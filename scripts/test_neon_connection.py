import os
import sys

NEON_URL = os.environ.get('DATABASE_URL') or 'postgresql://neondb_owner:npg_DBbTwA9SJz4o@ep-odd-breeze-a12hah7r-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

print('Using DATABASE_URL:', NEON_URL)

try:
    import psycopg2
except Exception as e:
    print('psycopg2 not installed. Install with: pip install psycopg2-binary')
    sys.exit(1)

try:
    conn = psycopg2.connect(NEON_URL)
    cur = conn.cursor()
    cur.execute('SELECT version();')
    v = cur.fetchone()
    print('Postgres version:', v)
    cur.close()
    conn.close()
    print('Connection successful')
except Exception as e:
    print('Connection failed:', e)
    sys.exit(2)
