from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, session, flash, abort
import os
import requests
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
import hashlib
import time
import random
import string

# 加载环境变量
load_dotenv()

app = Flask(__name__, static_folder='.', template_folder='.')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "visionary-app-fixed-secret-key")  # 使用环境变量或固定值

# 设置登录管理器
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# OAuth配置
oauth = OAuth(app)

# Coze API配置
API_KEY = os.getenv("COZE_API_KEY")
WORKFLOW_ID = os.getenv("COZE_WORKFLOW_ID")
COZE_API_URL = os.getenv("COZE_API_URL")

# Supabase 配置
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 用户类
class User(UserMixin):
    def __init__(self, id, username, email, avatar_url=None):
        self.id = id
        self.username = username
        self.email = email
        self.avatar_url = avatar_url

@login_manager.user_loader
def load_user(user_id):
    try:
        # 先查询profiles表获取用户详细信息
        user_data = supabase.table("profiles").select("*").eq("id", user_id).execute()
        if user_data.data and len(user_data.data) > 0:
            user = user_data.data[0]
            return User(user["id"], user["username"], user["email"], user["avatar_url"])
        return None
    except Exception as e:
        print(f"Error loading user: {e}")
        return None

# 主页路由
@app.route('/')
def index():
    return render_template('index.html')

# 创建页面路由
@app.route('/create')
@app.route('/create.html')
@login_required
def create():
    """生成图片页面路由，需要用户登录"""
    print(f"允许用户{current_user.username}访问create页面")
    return render_template('create.html')

# 登录页面路由重定向到主页
@app.route('/login')
def login():
    # Capture the 'next' query parameter if present and store in session
    next_url = request.args.get('next')
    if next_url:
        session['next'] = next_url
    else:
        # If accessed directly without 'next', default to create page after login
        session['next'] = url_for('create') 
        
    # Redirect to the main page signup section
    return redirect(url_for('index', _anchor='signup'))

# 登录
@app.route('/login', methods=['POST'])
def login_view():
    try:
        email = request.form.get('email')
        password = request.form.get('password')
        
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user_data = response.user
        
        # 创建并登录用户
        user = load_user(user_data.id)
        if user:
            login_user(user)
            # Check session for the next page
            next_page = session.pop('next', None) # Use 'next', pop it
            if next_page:
                # Basic validation: prevent open redirect vulnerability
                # Only redirect if it's a local path
                if next_page.startswith('/') or next_page.startswith(request.host_url):
                    print(f"登录成功，重定向到: {next_page}")
                    return redirect(next_page)
                else:
                    print(f"警告：检测到潜在的开放重定向，目标: {next_page}。将重定向到默认页面。")
                    # Fallback to default if next_page is suspicious
                    return redirect(url_for('create'))
            else:
                 # Default redirect after login if no specific next page
                print("登录成功，无特定 next 页面，重定向到 create")
                return redirect(url_for('create')) 
        else:
            flash('用户加载失败')
            return redirect(url_for('index', _anchor='signup'))
        
    except Exception as e:
        # More specific error handling could be added here based on Supabase exceptions
        print(f"登录异常: {e}")
        flash(f'登录失败: 邮箱或密码错误') # Generic message for security
        return redirect(url_for('index', _anchor='signup'))

# 用户历史记录
@app.route('/history')
@login_required
def history():
    # 重定向到统一历史页面
    return redirect(url_for('unified_history'))

# 静态文件服务
@app.route('/image/<path:filename>')
def serve_image(filename):
    return send_from_directory('image', filename)

# 图像生成API
@app.route('/generate-image', methods=['POST'])
def generate_image():
    try:
        # 获取前端发送的描述文本
        data = request.json
        description = data.get('description', '')
        style = data.get('style', 'default')
        
        # 将描述和风格组合成一个完整的描述字符串
        combined_description = f"{description}，{style}"
        
        # 调用Coze API生成图片
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "parameters": {
                "input": combined_description
            },
            "workflow_id": WORKFLOW_ID
        }
        
        response = requests.post(COZE_API_URL, headers=headers, json=payload)
        response_json = response.json()
        
        # 解析返回结果，获取图片URL
        if response_json.get('code') == 0:
            response_data = response_json.get('data', '{}')
            
            # 如果response_data是字符串，尝试解析为JSON
            if isinstance(response_data, str):
                try:
                    parsed_data = json.loads(response_data)
                    # 检查所有o1到o6字段，找出非空的链接
                    image_url = ''
                    for i in range(1, 7):
                        field_key = f'o{i}'
                        field_value = parsed_data.get(field_key, '')
                        if field_value and field_value.startswith('http'):
                            image_url = field_value
                            break
                    
                    # 如果用户已登录，保存到历史记录
                    if current_user.is_authenticated:
                        try:
                            # 保存到数据库
                            image_data = {
                                "user_id": current_user.id,
                                "prompt": description,
                                "style": style,
                                "image_url": image_url
                            }
                            supabase.table("image_history").insert(image_data).execute()
                        except Exception as db_error:
                            print(f"保存历史记录失败: {db_error}")
                    
                    return jsonify({
                        'success': True,
                        'image_url': image_url
                    })
                except json.JSONDecodeError:
                    return jsonify({
                        'success': False,
                        'error': '解析API响应失败'
                    }), 500
            else:
                # 如果response_data已经是字典
                image_url = ''
                for i in range(1, 7):
                    field_key = f'o{i}'
                    field_value = response_data.get(field_key, '')
                    if field_value and field_value.startswith('http'):
                        image_url = field_value
                        break
                
                # 如果用户已登录，保存到历史记录
                if current_user.is_authenticated:
                    try:
                        # 保存到数据库
                        image_data = {
                            "user_id": current_user.id,
                            "prompt": description,
                            "style": style,
                            "image_url": image_url
                        }
                        supabase.table("image_history").insert(image_data).execute()
                    except Exception as db_error:
                        print(f"保存历史记录失败: {db_error}")
                
                return jsonify({
                    'success': True,
                    'image_url': image_url
                })
        else:
            return jsonify({
                'success': False,
                'error': f"API调用失败: {response_json.get('msg', '未知错误')}"
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

# 邮箱注册和登录
@app.route('/email-auth', methods=['POST'])
def email_auth():
    try:
        email = request.form.get('email')
        password = request.form.get('password')
        action = request.form.get('action')
        
        if not email or not password:
            flash('请输入邮箱和密码')
            return redirect(url_for('index', _anchor='signup'))
            
        if action == 'register':
            # 使用Supabase Auth API进行注册
            try:
                auth_response = supabase.auth.sign_up({
                    "email": email,
                    "password": password,
                    "options": {
                        "data": {
                            "name": email.split('@')[0],  # 使用邮箱前缀作为默认用户名
                            "provider": "email"
                        }
                    }
                })
                
                if auth_response.user:
                    # 等待触发器自动创建profile记录
                    # 登录用户
                    login_response = supabase.auth.sign_in_with_password({
                        "email": email,
                        "password": password
                    })
                    
                    if login_response.user:
                        # 获取用户资料
                        profile_data = supabase.table("profiles").select("*").eq("id", login_response.user.id).execute()
                        if profile_data.data and len(profile_data.data) > 0:
                            profile = profile_data.data[0]
                            user_obj = User(profile["id"], profile["username"], profile["email"], profile["avatar_url"])
                            login_user(user_obj)
                            # Use 'next' from session for redirection
                            next_page = session.pop('next', url_for('create')) # Use 'next', pop it
                            # Basic validation to prevent open redirect
                            if next_page.startswith('/') or next_page.startswith(request.host_url):
                                print(f"注册并登录成功，重定向到: {next_page}")
                                return redirect(next_page)
                            else:
                                print(f"警告：检测到潜在的开放重定向，目标: {next_page}。将重定向到默认页面。")
                                return redirect(url_for('create')) # Fallback
                    
                    flash('注册成功，请登录')
                    return redirect(url_for('index', _anchor='signup'))
                else:
                    flash('注册失败，请稍后再试')
                    return redirect(url_for('index', _anchor='signup'))
            except Exception as e:
                if "User already registered" in str(e):
                    flash('该邮箱已被注册')
                else:
                    flash(f'注册失败: {str(e)}')
                return redirect(url_for('index', _anchor='signup'))
                
        elif action == 'login':
            # Restore login functionality here
            try:
                login_response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                
                if login_response.user:
                    # A valid login session was created
                    # 获取用户资料
                    profile_data = supabase.table("profiles").select("*").eq("id", login_response.user.id).execute()
                    if profile_data.data and len(profile_data.data) > 0:
                        profile = profile_data.data[0]
                        user_obj = User(profile["id"], profile["username"], profile["email"], profile["avatar_url"])
                        login_user(user_obj)
                        
                        # Correctly handle redirection using session['next']
                        next_page = session.pop('next', url_for('create')) 
                        if next_page.startswith('/') or next_page.startswith(request.host_url):
                            print(f"邮箱/密码登录成功，重定向到: {next_page}")
                            return redirect(next_page)
                        else:
                            print(f"警告：检测到潜在的开放重定向，目标: {next_page}。将重定向到默认页面。")
                            return redirect(url_for('create')) # Fallback
                    else:
                        # This case might happen if profile trigger failed, unlikely but possible
                        flash('用户资料加载失败，请重试')
                        # Log out the user if profile loading fails after successful auth
                        supabase.auth.sign_out()
                        return redirect(url_for('index', _anchor='signup'))
                else:
                    # Supabase sign_in_with_password itself failed (wrong email/password)
                    # The exception block below will likely catch this via Supabase specific errors
                    # But we can add a flash message here too for clarity if needed.
                    # flash('邮箱或密码错误') # Redundant if exception is caught
                    pass # Let the exception handler deal with it

            except Exception as e:
                 # More specific error handling could be added here based on Supabase exceptions
                print(f"邮箱/密码登录异常: {e}")
                flash(f'登录失败: 邮箱或密码错误') # Generic message for security
                return redirect(url_for('index', _anchor='signup'))
            # Default redirect if something unexpected happens within the try block before redirection
            return redirect(url_for('index', _anchor='signup'))

        else:
            flash('无效的操作')
            return redirect(url_for('index', _anchor='signup'))
            
    except Exception as e:
        flash(f'发生错误: {str(e)}')
        return redirect(url_for('index', _anchor='signup'))

# 调试路由
@app.route('/debug-login')
def debug_login():
    """调试路由，用于检查当前用户的登录状态和session信息"""
    debug_info = {
        'logged_in': current_user.is_authenticated,
        'session_keys': list(session.keys()) if session else [],
        'app_secret_fixed': app.secret_key == os.urandom(24)  # False表示使用了固定的密钥
    }
    
    if current_user.is_authenticated:
        debug_info.update({
            'user_id': current_user.id,
            'username': current_user.username,
            'email': current_user.email
        })
    
    return jsonify(debug_info)

# 登出
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# 卡片生成页面
@app.route('/create-card')
@login_required
def create_card():
    return render_template('create-card.html')

# 卡片生成API
@app.route('/generate-card', methods=['POST'])
def generate_card():
    try:
        # 获取前端发送的描述文本和风格
        data = request.json
        content = data.get('content', '')
        style = data.get('style', 'default')
        
        # 将内容和风格组合成一个完整的描述字符串
        combined_description = f"{content}，{style}"
        
        # 从环境变量获取API密钥
        dify_card_api_key = os.getenv("DIFY_CARD_API_KEY")
        if not dify_card_api_key:
            print("错误：DIFY_CARD_API_KEY 环境变量未设置！")
            return jsonify({'success': False, 'error': '服务器配置错误'}), 500
            
        print(f"使用API密钥: {dify_card_api_key}")
        
        headers = {
            "Authorization": f"Bearer {dify_card_api_key}", 
            "Content-Type": "application/json"
        }
        
        # 修改请求格式，使用正确的inputs格式
        payload = {
            "inputs": {"query": combined_description},  # 正确的inputs格式
            "query": combined_description,
            "response_mode": "blocking",  # 使用blocking模式
            "user": current_user.id if current_user.is_authenticated else "anonymous"
        }
        
        dify_api_url = "https://api.dify.ai/v1/chat-messages"
        print(f"正在调用Dify API: {dify_api_url}")
        print(f"请求负载: {json.dumps(payload)}")
        
        response = requests.post(dify_api_url, headers=headers, json=payload)
        print(f"Dify API响应状态码: {response.status_code}")
        
        # 打印原始响应文本
        raw_response = response.text
        print(f"原始响应: {raw_response}")
        
        # 尝试解析JSON
        try:
            response_json = response.json()
            print(f"解析后的JSON响应: {json.dumps(response_json)}")
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            return jsonify({
                'success': False,
                'error': f'API返回非JSON格式: {raw_response[:200]}...'
            }), 500
        
        # 解析返回结果，获取HTML代码
        html_code = None  # 初始化HTML代码变量
        
        if response_json.get('answer'):
            # 获取原始回答文本
            raw_answer = response_json.get('answer')
            print(f"提取的answer: {raw_answer[:200]}...")
            
            # 默认使用原始回答
            html_code = raw_answer
            
            # 如果答案包含markdown代码块格式的HTML
            if raw_answer.startswith('```html') and '```' in raw_answer[7:]:
                # 去除前面的 ```html 和后面的 ```
                html_start = raw_answer.find('```html') + 7
                html_end = raw_answer.rfind('```')
                if html_end > html_start:
                    html_code = raw_answer[html_start:html_end].strip()
                    print(f"从markdown代码块中提取HTML: {html_code[:200]}...")
            
            # 尝试提取完整的HTML文档，假如包含DOCTYPE和结束标签
            elif '<!DOCTYPE html>' in raw_answer and '</html>' in raw_answer:
                html_start = raw_answer.find('<!DOCTYPE html>')
                html_end = raw_answer.rfind('</html>') + 7  # 包含</html>标签
                if html_end > html_start:
                    html_code = raw_answer[html_start:html_end].strip()
                    print(f"提取完整HTML文档: {html_code[:200]}...")
            
            # 检查答案是否为JSON格式的字符串
            else:
                try:
                    # 尝试解析JSON
                    json_data = json.loads(raw_answer)
                    print(f"answer是JSON格式，解析后: {json.dumps(json_data)}")
                    
                    # 如果是JSON格式，提取HTML内容
                    if isinstance(json_data, dict):
                        if json_data.get('html'):
                            html_code = json_data.get('html')
                            print(f"从JSON中提取到html字段: {html_code[:200]}...")
                        elif json_data.get('content'):
                            html_code = json_data.get('content')
                            print(f"从JSON中提取到content字段: {html_code[:200]}...")
                        # 可能的其他字段名
                        elif json_data.get('data'):
                            html_code = json_data.get('data')
                            print(f"从JSON中提取到data字段: {html_code[:200]}...")
                        elif json_data.get('card'):
                            html_code = json_data.get('card')
                            print(f"从JSON中提取到card字段: {html_code[:200]}...")
                except json.JSONDecodeError:
                    # 不是JSON格式，使用原始答案
                    print("answer不是JSON格式，使用原始内容")
                    pass
        
        # 尝试从其他字段提取HTML
        elif response_json.get('data'):
            data_field = response_json.get('data')
            print(f"发现data字段: {data_field}")
            
            # 检查data字段是否是字符串形式的JSON
            if isinstance(data_field, str):
                try:
                    data_json = json.loads(data_field)
                    print(f"data字段是JSON字符串: {json.dumps(data_json)}")
                    
                    # 检查解析后的JSON中是否有HTML内容
                    if isinstance(data_json, dict):
                        for key in ['html', 'content', 'card', 'result']:
                            if data_json.get(key):
                                html_code = data_json.get(key)
                                print(f"从data字段JSON中提取到{key}: {html_code[:200]}...")
                                break
                except json.JSONDecodeError:
                    # data不是JSON字符串
                    print("data字段不是JSON字符串")
            elif isinstance(data_field, dict):
                print(f"data字段是字典: {json.dumps(data_field)}")
                
                # 直接检查字典中是否有HTML内容
                for key in ['html', 'content', 'card', 'result']:
                    if data_field.get(key):
                        html_code = data_field.get(key)
                        print(f"从data字典中提取到{key}: {html_code[:200]}...")
                        break
        
        # 如果没有找到有效的HTML代码
        if not html_code:
            return jsonify({
                'success': False,
                'error': 'API返回结果格式不正确',
                'response': response_json
            }), 500
        
        # 如果用户已登录，保存到历史记录
        if current_user.is_authenticated:
            try:
                # 保存到数据库
                card_data = {
                    "user_id": current_user.id,
                    "content": content,
                    "style": style,
                    "html_code": html_code
                }
                
                print(f"正在保存卡片数据，用户ID: {current_user.id}")
                
                # 显式使用服务器端JWT令牌进行数据库操作
                result = supabase.auth.get_user()
                if result and hasattr(result, 'user') and result.user:
                    print(f"已获取当前用户认证信息: {result.user.id}")
                else:
                    print("警告：无法获取当前用户认证信息，尝试使用current_user.id继续")
                
                result = supabase.table("card_history").insert(card_data).execute()
                print(f"插入结果: {result.data if hasattr(result, 'data') else '没有数据'}")
                print(f"成功保存卡片历史记录")
            except Exception as db_error:
                import traceback
                error_details = traceback.format_exc()
                print(f"保存卡片历史记录失败: {db_error}\n{error_details}")
        
        return jsonify({
            'success': True,
            'html_code': html_code
        })
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"卡片生成异常: {str(e)}\n{error_details}")
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 卡片历史记录
@app.route('/card-history')
def card_history():
    # 如果用户未登录，保存目标页面到session
    if not current_user.is_authenticated:
        session['next'] = url_for('unified_history')
        return redirect(url_for('index', _anchor='signup'))
    # 重定向到统一历史页面
    return redirect(url_for('unified_history'))

# 统一历史页面
@app.route('/unified-history')
@login_required
def unified_history():
    # 当使用@login_required时，会自动处理重定向
    return render_template('unified-history.html')

# 图片历史API
@app.route('/api/image-history')
@login_required
def api_image_history():
    try:
        # 获取用户的图片生成历史记录
        history_data = supabase.table("image_history")\
            .select("*")\
            .eq("user_id", current_user.id)\
            .execute()
        
        # 在Python中手动排序结果
        sorted_data = sorted(history_data.data, key=lambda x: x.get('created_at', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'images': sorted_data
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"获取图片历史记录失败: {str(e)}\n{error_details}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 卡片历史API
@app.route('/api/card-history')
@login_required
def api_card_history():
    try:
        # 获取用户的卡片生成历史记录
        history_data = supabase.table("card_history")\
            .select("*")\
            .eq("user_id", current_user.id)\
            .execute()
        
        # 在Python中手动排序结果
        sorted_data = sorted(history_data.data, key=lambda x: x.get('created_at', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'cards': sorted_data
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"获取卡片历史记录失败: {str(e)}\n{error_details}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 网页生成页面
@app.route('/create-webpage')
@login_required
def create_webpage():
    return render_template('create-webpage.html')

# 网页生成API
@app.route('/generate-webpage', methods=['POST'])
def generate_webpage():
    try:
        # 获取前端发送的描述文本和风格
        data = request.json
        content = data.get('content', '')
        style = data.get('style', 'default')
        
        # 将内容和风格组合成一个完整的描述字符串
        combined_description = f"{content}，{style}"
        
        # 从环境变量获取API密钥
        dify_webpage_api_key = os.getenv("DIFY_WEBPAGE_API_KEY")
        if not dify_webpage_api_key:
            print("错误：DIFY_WEBPAGE_API_KEY 环境变量未设置！")
            return jsonify({'success': False, 'error': '服务器配置错误'}), 500
            
        print(f"使用API密钥: {dify_webpage_api_key}")
        
        headers = {
            "Authorization": f"Bearer {dify_webpage_api_key}", 
            "Content-Type": "application/json"
        }
        
        # 修改请求格式，使用正确的inputs格式
        payload = {
            "inputs": {"query": combined_description},  # 正确的inputs格式
            "query": combined_description,
            "response_mode": "blocking",  # 使用blocking模式
            "user": current_user.id if current_user.is_authenticated else "anonymous"
        }
        
        dify_api_url = "https://api.dify.ai/v1/chat-messages"
        print(f"正在调用Dify API: {dify_api_url}")
        print(f"请求负载: {json.dumps(payload)}")
        
        response = requests.post(dify_api_url, headers=headers, json=payload)
        print(f"Dify API响应状态码: {response.status_code}")
        
        # 打印原始响应文本
        raw_response = response.text
        print(f"原始响应: {raw_response}")
        
        # 尝试解析JSON
        try:
            response_json = response.json()
            print(f"解析后的JSON响应: {json.dumps(response_json)}")
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            return jsonify({
                'success': False,
                'error': f'API返回非JSON格式: {raw_response[:200]}...'
            }), 500
        
        # 解析返回结果，获取HTML代码
        html_code = None  # 初始化HTML代码变量
        
        if response_json.get('answer'):
            # 获取原始回答文本
            raw_answer = response_json.get('answer')
            print(f"提取的answer: {raw_answer[:200]}...")
            
            # 默认使用原始回答
            html_code = raw_answer
            
            # 如果答案包含markdown代码块格式的HTML
            if raw_answer.startswith('```html') and '```' in raw_answer[7:]:
                # 去除前面的 ```html 和后面的 ```
                html_start = raw_answer.find('```html') + 7
                html_end = raw_answer.rfind('```')
                if html_end > html_start:
                    html_code = raw_answer[html_start:html_end].strip()
                    print(f"从markdown代码块中提取HTML: {html_code[:200]}...")
            
            # 尝试提取完整的HTML文档，假如包含DOCTYPE和结束标签
            elif '<!DOCTYPE html>' in raw_answer and '</html>' in raw_answer:
                html_start = raw_answer.find('<!DOCTYPE html>')
                html_end = raw_answer.rfind('</html>') + 7  # 包含</html>标签
                if html_end > html_start:
                    html_code = raw_answer[html_start:html_end].strip()
                    print(f"提取完整HTML文档: {html_code[:200]}...")
            
            # 检查答案是否为JSON格式的字符串
            else:
                try:
                    # 尝试解析JSON
                    json_data = json.loads(raw_answer)
                    print(f"answer是JSON格式，解析后: {json.dumps(json_data)}")
                    
                    # 如果是JSON格式，提取HTML内容
                    if isinstance(json_data, dict):
                        if json_data.get('html'):
                            html_code = json_data.get('html')
                            print(f"从JSON中提取到html字段: {html_code[:200]}...")
                        elif json_data.get('content'):
                            html_code = json_data.get('content')
                            print(f"从JSON中提取到content字段: {html_code[:200]}...")
                        # 可能的其他字段名
                        elif json_data.get('data'):
                            html_code = json_data.get('data')
                            print(f"从JSON中提取到data字段: {html_code[:200]}...")
                        elif json_data.get('webpage'):
                            html_code = json_data.get('webpage')
                            print(f"从JSON中提取到webpage字段: {html_code[:200]}...")
                except json.JSONDecodeError:
                    # 不是JSON格式，使用原始答案
                    print("answer不是JSON格式，使用原始内容")
                    pass
        
        # 尝试从其他字段提取HTML
        elif response_json.get('data'):
            data_field = response_json.get('data')
            print(f"发现data字段: {data_field}")
            
            # 检查data字段是否是字符串形式的JSON
            if isinstance(data_field, str):
                try:
                    data_json = json.loads(data_field)
                    print(f"data字段是JSON字符串: {json.dumps(data_json)}")
                    
                    # 检查解析后的JSON中是否有HTML内容
                    if isinstance(data_json, dict):
                        for key in ['html', 'content', 'webpage', 'result']:
                            if data_json.get(key):
                                html_code = data_json.get(key)
                                print(f"从data字段JSON中提取到{key}: {html_code[:200]}...")
                                break
                except json.JSONDecodeError:
                    # data不是JSON字符串
                    print("data字段不是JSON字符串")
            elif isinstance(data_field, dict):
                print(f"data字段是字典: {json.dumps(data_field)}")
                
                # 直接检查字典中是否有HTML内容
                for key in ['html', 'content', 'webpage', 'result']:
                    if data_field.get(key):
                        html_code = data_field.get(key)
                        print(f"从data字典中提取到{key}: {html_code[:200]}...")
                        break
        
        # 如果没有找到有效的HTML代码
        if not html_code:
            return jsonify({
                'success': False,
                'error': 'API返回结果格式不正确',
                'response': response_json
            }), 500
        
        # 如果用户已登录，保存到历史记录
        if current_user.is_authenticated:
            try:
                # 首先生成一个新的UUID作为网页ID
                webpage_id = str(uuid.uuid4())
                
                # 保存到数据库，设置webpage_url为查看页面的URL
                webpage_data = {
                    "id": webpage_id,  # 使用生成的UUID
                    "user_id": current_user.id,
                    "content": content,
                    "style": style,
                    "html_code": html_code,
                    "title": f"网页 - {content[:30]}..." if len(content) > 30 else f"网页 - {content}",
                    "webpage_url": f"/view-webpage/{webpage_id}"  # 设置为查看页面的URL
                }
                
                print(f"正在保存网页数据，用户ID: {current_user.id}")
                
                result = supabase.table("webpage_history").insert(webpage_data).execute()
                print(f"插入结果: {result.data if hasattr(result, 'data') else '没有数据'}")
                print(f"成功保存网页历史记录")
            except Exception as db_error:
                import traceback
                error_details = traceback.format_exc()
                print(f"保存网页历史记录失败: {db_error}\n{error_details}")
        
        return jsonify({
            'success': True,
            'html_code': html_code
        })
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"网页生成异常: {str(e)}\n{error_details}")
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 网页历史记录
@app.route('/webpage-history')
def webpage_history():
    # 如果用户未登录，保存目标页面到session
    if not current_user.is_authenticated:
        session['next'] = url_for('unified_history')
        return redirect(url_for('index', _anchor='signup'))
    # 重定向到统一历史页面
    return redirect(url_for('unified_history'))

@app.route('/api/webpage-history')
@login_required
def api_webpage_history():
    try:
        # 获取用户的网页生成历史记录
        history_data = supabase.table('webpage_history')\
            .select('*')\
            .eq('user_id', current_user.id)\
            .execute()
        
        # 在Python中手动排序结果
        sorted_data = sorted(history_data.data, key=lambda x: x.get('created_at', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'webpages': sorted_data
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"获取网页历史记录失败: {str(e)}\n{error_details}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 查看保存的网页
@app.route('/view-webpage/<webpage_id>')
def view_webpage(webpage_id):
    try:
        # 从数据库获取网页数据
        response = supabase.table('webpage_history').select('*').eq('id', webpage_id).execute()
        
        if not response.data or len(response.data) == 0:
            return render_template('error.html', message="未找到该网页"), 404
        
        webpage = response.data[0]
        
        # 如果是未登录用户或者不是网页的所有者，检查是否是公开分享的网页
        if not current_user.is_authenticated or current_user.id != webpage['user_id']:
            # 检查是否有公开分享的记录
            share_response = supabase.table('shared_webpages').select('*')\
                .eq('webpage_id', webpage_id)\
                .eq('is_public', True)\
                .execute()
            
            if not share_response.data or len(share_response.data) == 0:
                return render_template('error.html', message="您没有权限查看此网页"), 403
        
        # 直接返回HTML内容
        return webpage['html_code']
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"查看网页异常: {str(e)}\n{error_details}")
        return render_template('error.html', message=f"查看网页时发生错误: {str(e)}"), 500

# 获取网页HTML代码的API
@app.route('/api/webpage-html/<webpage_id>')
def api_webpage_html(webpage_id):
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': '未登录'}), 401
    
    try:
        # 从数据库获取网页数据
        response = supabase.table('webpage_history').select('*').eq('id', webpage_id).execute()
        
        if not response.data or len(response.data) == 0:
            return jsonify({'success': False, 'message': '未找到网页'}), 404
        
        webpage = response.data[0]
        
        # 检查用户是否有权限访问该网页
        if webpage['user_id'] != current_user.id:
            return jsonify({'success': False, 'message': '无权访问'}), 403
        
        # 返回HTML代码
        return jsonify({
            'success': True,
            'html_code': webpage['html_code'],
            'title': webpage.get('title', '未命名网页')
        })
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"获取网页HTML代码异常: {str(e)}\n{error_details}")
        return jsonify({'success': False, 'message': f'获取HTML代码失败: {str(e)}'}), 500

# 删除图片历史记录API
@app.route('/api/delete-image/<image_id>', methods=['DELETE'])
@login_required
def delete_image(image_id):
    try:
        # 验证image_id是否为有效的UUID
        try:
            uuid.UUID(image_id)
        except ValueError:
            return jsonify({'success': False, 'error': '无效的图片ID'}), 400
        
        # 删除数据库中的记录
        # 首先检查记录是否存在并且属于当前用户
        image_data = supabase.table("image_history")\
            .select("id, user_id")\
            .eq("id", image_id)\
            .eq("user_id", current_user.id)\
            .execute()
        
        if not image_data.data or len(image_data.data) == 0:
            return jsonify({'success': False, 'error': '图片记录未找到或无权限'}), 404
        
        # 执行删除操作
        delete_response = supabase.table("image_history")\
            .delete()\
            .eq("id", image_id)\
            .execute()
        
        # 检查删除是否成功 (Supabase V2 可能返回 data 列表，V1 可能没有明确的成功标志)
        # 这里假设没有错误就是成功
        print(f"删除图片 {image_id} 响应: {delete_response}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"删除图片历史记录失败: {str(e)}\n{error_details}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 删除卡片历史记录API
@app.route('/api/delete-card/<card_id>', methods=['DELETE'])
@login_required
def delete_card(card_id):
    try:
        # 验证card_id是否为有效的UUID
        try:
            uuid.UUID(card_id)
        except ValueError:
            return jsonify({'success': False, 'error': '无效的卡片ID'}), 400
        
        # 检查记录是否存在并且属于当前用户
        card_data = supabase.table("card_history")\
            .select("id, user_id")\
            .eq("id", card_id)\
            .eq("user_id", current_user.id)\
            .execute()
        
        if not card_data.data or len(card_data.data) == 0:
            return jsonify({'success': False, 'error': '卡片记录未找到或无权限'}), 404
        
        # 执行删除操作
        delete_response = supabase.table("card_history")\
            .delete()\
            .eq("id", card_id)\
            .execute()
        
        print(f"删除卡片 {card_id} 响应: {delete_response}")
        return jsonify({'success': True})
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"删除卡片历史记录失败: {str(e)}\n{error_details}")
        return jsonify({'success': False, 'error': str(e)}), 500

# 删除网页历史记录API
@app.route('/api/delete-webpage/<webpage_id>', methods=['DELETE'])
@login_required
def delete_webpage(webpage_id):
    try:
        # 验证webpage_id是否为有效的UUID
        try:
            uuid.UUID(webpage_id)
        except ValueError:
            return jsonify({'success': False, 'error': '无效的网页ID'}), 400
        
        # 检查记录是否存在并且属于当前用户
        webpage_data = supabase.table("webpage_history")\
            .select("id, user_id")\
            .eq("id", webpage_id)\
            .eq("user_id", current_user.id)\
            .execute()
        
        if not webpage_data.data or len(webpage_data.data) == 0:
            return jsonify({'success': False, 'error': '网页记录未找到或无权限'}), 404
        
        # 首先，删除相关的共享记录 (如果存在)
        share_delete_response = supabase.table("shared_webpages")\
            .delete()\
            .eq("webpage_id", webpage_id)\
            .execute()
        print(f"删除网页 {webpage_id} 的共享记录响应: {share_delete_response}")

        # 然后，删除网页历史记录本身
        delete_response = supabase.table("webpage_history")\
            .delete()\
            .eq("id", webpage_id)\
            .execute()
        
        print(f"删除网页 {webpage_id} 响应: {delete_response}")
        return jsonify({'success': True})
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"删除网页历史记录失败: {str(e)}\n{error_details}")
        return jsonify({'success': False, 'error': str(e)}), 500

# 提交事务
if __name__ == '__main__':
    app.run(debug=bool(os.getenv("FLASK_DEBUG", "True") == "True"), 
            port=int(os.getenv("FLASK_PORT", 5000)))