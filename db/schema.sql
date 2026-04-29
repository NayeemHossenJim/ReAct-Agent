DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;

CREATE TABLE products (
  id          SERIAL PRIMARY KEY,
  name        TEXT    NOT NULL,
  category    TEXT    NOT NULL,
  price       NUMERIC(10, 2) NOT NULL,
  stock       INTEGER NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE orders (
  id          SERIAL PRIMARY KEY,
  product_id  INTEGER REFERENCES products(id),
  quantity    INTEGER NOT NULL,
  total       NUMERIC(10, 2) NOT NULL,
  status      TEXT    NOT NULL DEFAULT 'pending',
  ordered_at  TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO products (name, category, price, stock) VALUES
  ('Wireless Keyboard', 'Electronics', 49.99, 120),
  ('USB-C Hub',         'Electronics', 34.99,  85),
  ('Notebook A5',       'Stationery',   8.99, 300),
  ('Mechanical Pencil', 'Stationery',   4.49, 500),
  ('Desk Lamp',         'Furniture',   29.99,  60);

INSERT INTO orders (product_id, quantity, total, status, ordered_at) VALUES
  (1, 2, 99.98, 'completed', NOW() - INTERVAL '3 days'),
  (2, 1, 34.99, 'completed', NOW() - INTERVAL '1 day'),
  (3, 5, 44.95, 'pending',   NOW() - INTERVAL '2 hours'),
  (1, 1, 49.99, 'shipped',   NOW() - INTERVAL '5 days'),
  (5, 3, 89.97, 'cancelled', NOW() - INTERVAL '10 days');