-- 启用UUID扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 开始事务
BEGIN;

-- 创建用户配置文件表
CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID REFERENCES auth.users(id) PRIMARY KEY,
  username TEXT,
  avatar_url TEXT,
  email TEXT,
  provider TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 创建唯一约束（单独创建以避免表创建失败）
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint 
    WHERE conname = 'profiles_username_key' AND conrelid = 'public.profiles'::regclass
  ) THEN
    ALTER TABLE public.profiles ADD CONSTRAINT profiles_username_key UNIQUE (username);
  END IF;
  
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint 
    WHERE conname = 'profiles_email_key' AND conrelid = 'public.profiles'::regclass
  ) THEN
    ALTER TABLE public.profiles ADD CONSTRAINT profiles_email_key UNIQUE (email);
  END IF;
END
$$;

-- 创建图片历史记录表
CREATE TABLE IF NOT EXISTS public.image_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  prompt TEXT NOT NULL,
  style TEXT NOT NULL,
  image_url TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 创建收藏表
CREATE TABLE IF NOT EXISTS public.favorites (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  image_id UUID REFERENCES public.image_history(id) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 创建卡片历史记录表
CREATE TABLE IF NOT EXISTS public.card_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  content TEXT NOT NULL,
  style TEXT NOT NULL,
  html_code TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 创建网页历史记录表
CREATE TABLE IF NOT EXISTS public.webpage_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  content TEXT NOT NULL,
  style TEXT NOT NULL,
  html_code TEXT NOT NULL,
  webpage_url TEXT NOT NULL,
  title TEXT,
  thumbnail_url TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 创建唯一约束
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint 
    WHERE conname = 'favorites_user_id_image_id_key' AND conrelid = 'public.favorites'::regclass
  ) THEN
    ALTER TABLE public.favorites ADD CONSTRAINT favorites_user_id_image_id_key UNIQUE (user_id, image_id);
  END IF;
END
$$;

-- 创建网页分享表
CREATE TABLE IF NOT EXISTS public.shared_webpages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  webpage_id UUID REFERENCES public.webpage_history(id) NOT NULL,
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  share_code TEXT NOT NULL UNIQUE,
  is_public BOOLEAN DEFAULT false,
  access_count INTEGER DEFAULT 0,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_shared_webpages_share_code ON public.shared_webpages(share_code);
CREATE INDEX IF NOT EXISTS idx_shared_webpages_user_id ON public.shared_webpages(user_id);

-- 设置RLS策略
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.image_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.favorites ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.card_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.webpage_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shared_webpages ENABLE ROW LEVEL SECURITY;

-- 删除可能存在的策略
DROP POLICY IF EXISTS "profiles_select_policy" ON public.profiles;
DROP POLICY IF EXISTS "profiles_update_policy" ON public.profiles;
DROP POLICY IF EXISTS "image_history_select_policy" ON public.image_history;
DROP POLICY IF EXISTS "image_history_insert_policy" ON public.image_history;
DROP POLICY IF EXISTS "image_history_delete_policy" ON public.image_history;
DROP POLICY IF EXISTS "favorites_select_policy" ON public.favorites;
DROP POLICY IF EXISTS "favorites_all_policy" ON public.favorites;
DROP POLICY IF EXISTS "card_history_select_policy" ON public.card_history;
DROP POLICY IF EXISTS "card_history_insert_policy" ON public.card_history;
DROP POLICY IF EXISTS "card_history_delete_policy" ON public.card_history;
DROP POLICY IF EXISTS "webpage_history_select_policy" ON public.webpage_history;
DROP POLICY IF EXISTS "webpage_history_insert_policy" ON public.webpage_history;
DROP POLICY IF EXISTS "webpage_history_delete_policy" ON public.webpage_history;
DROP POLICY IF EXISTS "webpage_history_update_policy" ON public.webpage_history;
DROP POLICY IF EXISTS "shared_webpages_select_policy" ON public.shared_webpages;
DROP POLICY IF EXISTS "shared_webpages_insert_policy" ON public.shared_webpages;
DROP POLICY IF EXISTS "shared_webpages_update_policy" ON public.shared_webpages;
DROP POLICY IF EXISTS "shared_webpages_delete_policy" ON public.shared_webpages;

-- 创建新策略
CREATE POLICY "profiles_select_policy" ON public.profiles
  FOR SELECT USING (true);

CREATE POLICY "profiles_update_policy" ON public.profiles
  FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "image_history_select_policy" ON public.image_history
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "image_history_insert_policy" ON public.image_history
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "image_history_delete_policy" ON public.image_history
  FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "favorites_select_policy" ON public.favorites
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "favorites_all_policy" ON public.favorites
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "card_history_select_policy" ON public.card_history
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "card_history_insert_policy" ON public.card_history
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "card_history_delete_policy" ON public.card_history
  FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "webpage_history_select_policy" ON public.webpage_history
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "webpage_history_insert_policy" ON public.webpage_history
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "webpage_history_delete_policy" ON public.webpage_history
  FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "webpage_history_update_policy" ON public.webpage_history
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "shared_webpages_select_policy" ON public.shared_webpages
  FOR SELECT USING (true);

CREATE POLICY "shared_webpages_insert_policy" ON public.shared_webpages
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "shared_webpages_update_policy" ON public.shared_webpages
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "shared_webpages_delete_policy" ON public.shared_webpages
  FOR DELETE USING (auth.uid() = user_id);

-- 创建触发器函数
CREATE OR REPLACE FUNCTION public.create_profile_for_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, username, avatar_url, email, provider)
  VALUES (
    new.id,
    COALESCE(new.raw_user_meta_data->>'name', split_part(new.email, '@', 1)),
    new.raw_user_meta_data->>'avatar_url',
    new.email,
    COALESCE(new.raw_user_meta_data->>'provider', 'email')
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 删除可能存在的触发器
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- 创建触发器
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.create_profile_for_user();

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_webpage_history_user_id ON public.webpage_history(user_id);
CREATE INDEX IF NOT EXISTS idx_webpage_history_created_at ON public.webpage_history(created_at DESC);

-- 创建更新时间戳触发器函数
CREATE OR REPLACE FUNCTION update_webpage_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建更新时间戳触发器
DROP TRIGGER IF EXISTS trigger_update_webpage_timestamp ON public.webpage_history;
CREATE TRIGGER trigger_update_webpage_timestamp
BEFORE UPDATE ON public.webpage_history
FOR EACH ROW EXECUTE FUNCTION update_webpage_timestamp();

-- 为公开分享的网页创建专门的查询函数
CREATE OR REPLACE FUNCTION public.get_public_shared_webpage(share_code_param TEXT)
RETURNS TABLE (
  id UUID,
  title TEXT,
  html_code TEXT,
  content TEXT,
  style TEXT,
  created_at TIMESTAMPTZ
) AS $$
BEGIN
  -- 更新访问计数
  UPDATE public.shared_webpages
  SET access_count = access_count + 1
  WHERE share_code = share_code_param
    AND (expires_at IS NULL OR expires_at > NOW())
    AND is_public = TRUE;

  -- 返回网页数据
  RETURN QUERY
  SELECT 
    w.id,
    w.title,
    w.html_code,
    w.content,
    w.style,
    w.created_at
  FROM public.webpage_history w
  JOIN public.shared_webpages s ON w.id = s.webpage_id
  WHERE s.share_code = share_code_param
    AND (s.expires_at IS NULL OR s.expires_at > NOW())
    AND s.is_public = TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 创建网页访问分析表
CREATE TABLE IF NOT EXISTS public.webpage_analytics (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  webpage_id UUID REFERENCES public.webpage_history(id) NOT NULL,
  share_id UUID REFERENCES public.shared_webpages(id),
  visitor_ip TEXT,
  user_agent TEXT,
  referrer TEXT,
  visit_duration INTEGER,
  country TEXT,
  device_type TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_webpage_analytics_webpage_id ON public.webpage_analytics(webpage_id);
CREATE INDEX IF NOT EXISTS idx_webpage_analytics_created_at ON public.webpage_analytics(created_at);

-- 设置RLS策略
ALTER TABLE public.webpage_analytics ENABLE ROW LEVEL SECURITY;

-- 删除可能存在的策略
DROP POLICY IF EXISTS "webpage_analytics_select_policy" ON public.webpage_analytics;
DROP POLICY IF EXISTS "webpage_analytics_insert_policy" ON public.webpage_analytics;

-- 创建策略
CREATE POLICY "webpage_analytics_select_policy" ON public.webpage_analytics
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.webpage_history wh
      WHERE wh.id = webpage_id AND wh.user_id = auth.uid()
    )
  );

CREATE POLICY "webpage_analytics_insert_policy" ON public.webpage_analytics
  FOR INSERT WITH CHECK (true);

-- 创建函数来获取网页分析摘要
CREATE OR REPLACE FUNCTION public.get_webpage_analytics_summary(webpage_id_param UUID)
RETURNS TABLE (
  total_visits INTEGER,
  unique_visitors INTEGER,
  avg_duration INTEGER,
  top_referrers JSONB,
  top_countries JSONB,
  top_devices JSONB,
  visits_by_day JSONB
) AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM public.webpage_history
    WHERE id = webpage_id_param AND user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'Unauthorized access to webpage analytics';
  END IF;

  RETURN QUERY
  WITH analytics AS (
    SELECT
      COUNT(*) AS total_visits,
      COUNT(DISTINCT visitor_ip) AS unique_visitors,
      COALESCE(AVG(visit_duration), 0)::INTEGER AS avg_duration,
      COALESCE(
        (SELECT jsonb_object_agg(referrer, count)
         FROM (
           SELECT referrer, COUNT(*) AS count
           FROM public.webpage_analytics
           WHERE webpage_id = webpage_id_param AND referrer IS NOT NULL
           GROUP BY referrer
           ORDER BY COUNT(*) DESC
           LIMIT 5
         ) AS top_refs
        ), '{}'::jsonb
      ) AS top_referrers,
      COALESCE(
        (SELECT jsonb_object_agg(country, count)
         FROM (
           SELECT country, COUNT(*) AS count
           FROM public.webpage_analytics
           WHERE webpage_id = webpage_id_param AND country IS NOT NULL
           GROUP BY country
           ORDER BY COUNT(*) DESC
           LIMIT 5
         ) AS top_countries
        ), '{}'::jsonb
      ) AS top_countries,
      COALESCE(
        (SELECT jsonb_object_agg(device_type, count)
         FROM (
           SELECT device_type, COUNT(*) AS count
           FROM public.webpage_analytics
           WHERE webpage_id = webpage_id_param AND device_type IS NOT NULL
           GROUP BY device_type
           ORDER BY COUNT(*) DESC
           LIMIT 5
         ) AS top_devices
        ), '{}'::jsonb
      ) AS top_devices,
      COALESCE(
        (SELECT jsonb_object_agg(date, count)
         FROM (
           SELECT 
             TO_CHAR(created_at, 'YYYY-MM-DD') AS date, 
             COUNT(*) AS count
           FROM public.webpage_analytics
           WHERE webpage_id = webpage_id_param
           GROUP BY TO_CHAR(created_at, 'YYYY-MM-DD')
           ORDER BY date DESC
           LIMIT 30
         ) AS visits_by_day
        ), '{}'::jsonb
      ) AS visits_by_day
    FROM public.webpage_analytics
    WHERE webpage_id = webpage_id_param
  )
  SELECT * FROM analytics;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 提交事务
COMMIT; 