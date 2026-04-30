-- db/init.sql
-- Demo schema — applied automatically by docker-compose on first startup.

-- Read-only agent user
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sql_agent_readonly') THEN
    CREATE ROLE sql_agent_readonly LOGIN PASSWORD 'readonly_password_change_me';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE sql_agent_demo TO sql_agent_readonly;
GRANT USAGE ON SCHEMA public TO sql_agent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sql_agent_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sql_agent_readonly;

-- Tables
CREATE TABLE IF NOT EXISTS public.customers (
    customer_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    segment       TEXT CHECK (segment IN ('enterprise', 'smb', 'consumer')),
    country       TEXT NOT NULL DEFAULT 'US',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS public.products (
    product_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    price         NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    cost          NUMERIC(10,2) NOT NULL CHECK (cost >= 0),
    sku           TEXT UNIQUE NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.orders (
    order_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id   UUID NOT NULL REFERENCES public.customers(customer_id),
    status        TEXT NOT NULL CHECK (status IN ('pending','processing','completed','cancelled','refunded')),
    amount        NUMERIC(12,2) NOT NULL,
    currency      CHAR(3) NOT NULL DEFAULT 'USD',
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.order_items (
    item_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id      UUID NOT NULL REFERENCES public.orders(order_id),
    product_id    UUID NOT NULL REFERENCES public.products(product_id),
    quantity      INT NOT NULL CHECK (quantity > 0),
    unit_price    NUMERIC(10,2) NOT NULL,
    discount_pct  NUMERIC(5,2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS public.reviews (
    review_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id    UUID NOT NULL REFERENCES public.products(product_id),
    customer_id   UUID NOT NULL REFERENCES public.customers(customer_id),
    rating        SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.support_tickets (
    ticket_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id   UUID NOT NULL REFERENCES public.customers(customer_id),
    subject       TEXT NOT NULL,
    description   TEXT,
    status        TEXT NOT NULL CHECK (status IN ('open','in_progress','resolved','closed')),
    priority      TEXT NOT NULL CHECK (priority IN ('low','medium','high','critical')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at   TIMESTAMPTZ
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_orders_customer  ON public.orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status    ON public.orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created   ON public.orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_order      ON public.order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_items_product    ON public.order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_reviews_product  ON public.reviews(product_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status   ON public.support_tickets(status, priority);

-- Seed data
INSERT INTO public.customers (name, email, segment, country) VALUES
    ('Acme Corp',       'billing@acme.com',       'enterprise', 'US'),
    ('GlobalTech Ltd',  'accounts@globaltech.io', 'enterprise', 'GB'),
    ('Sara Patel',      'sara.patel@gmail.com',   'consumer',   'IN'),
    ('Mountain Coffee', 'orders@mtncoffee.com',   'smb',        'US'),
    ('Nexus Dynamics',  'finance@nexusdyn.com',   'smb',        'DE')
ON CONFLICT DO NOTHING;

INSERT INTO public.products (name, category, price, cost, sku) VALUES
    ('Pro Analytics Suite',  'software', 299.00,  18.00, 'SW-001'),
    ('DataSync Connector',   'software',  49.00,   3.00, 'SW-002'),
    ('Enterprise Dashboard', 'software', 899.00,  55.00, 'SW-003'),
    ('USB-C Hub 7-Port',     'hardware',  79.95,  32.00, 'HW-001'),
    ('Wireless Keyboard',    'hardware',  59.99,  22.00, 'HW-002')
ON CONFLICT DO NOTHING;
