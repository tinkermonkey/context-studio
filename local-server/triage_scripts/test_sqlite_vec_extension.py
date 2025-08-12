import sqlite3
import os
import sqlite_vec

print("SQLite Version:", sqlite3.sqlite_version)
print("SQLite File:", sqlite3.__file__)

def main():
    db_path = "test_vec.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    print(f"Creating SQLite DB at {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        print("Enabling extension loading...")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        print("Extension loaded successfully!")
        # Try to create a virtual table using vec0
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS test_vec USING vec0(
                id TEXT PRIMARY KEY,
                embedding FLOAT[384]
            );
        """)
        print("Virtual table created successfully!")

        vec_version = conn.execute("select vec_version()").fetchone()
        print(f"vec_version={vec_version}")

        embedding = [0.1, 0.2, 0.3, 0.4]
        result = conn.execute('select vec_length(?)', [sqlite_vec.serialize_float32(embedding)])

        print(result.fetchone()[0]) # 4

        test_sql_1 = '''
create virtual table vec_examples using vec0(
  sample_embedding float[8]
);
'''
        test_sql_2 = '''
-- vectors can be provided as JSON or in a compact binary format
insert into vec_examples(rowid, sample_embedding)
  values
    (1, '[-0.200, 0.250, 0.341, -0.211, 0.645, 0.935, -0.316, -0.924]'),
    (2, '[0.443, -0.501, 0.355, -0.771, 0.707, -0.708, -0.185, 0.362]'),
    (3, '[0.716, -0.927, 0.134, 0.052, -0.669, 0.793, -0.634, -0.162]'),
    (4, '[-0.710, 0.330, 0.656, 0.041, -0.990, 0.726, 0.385, -0.958]');
'''
        test_sql_3 = '''
-- KNN style query
select
  rowid,
  distance
from vec_examples
where sample_embedding match '[0.890, 0.544, 0.825, 0.961, 0.358, 0.0196, 0.521, 0.175]'
order by distance
limit 2;
'''

        result = conn.execute(test_sql_1).fetchone()
        print(result)

        result = conn.execute(test_sql_2).fetchone()
        print(result)

        result = conn.execute(test_sql_3).fetchone()
        print(result)


        test_sql_1 = '''
create virtual table vec_examples_2 using vec0(
  sample_embedding float[8],
  another_embedding float[8]
);
'''
        test_sql_2 = '''
-- vectors can be provided as JSON or in a compact binary format
insert into vec_examples_2(rowid, sample_embedding, another_embedding)
  values
    (1, '[-0.200, 0.250, 0.341, -0.211, 0.645, 0.935, -0.316, -0.924]', '[-0.200, 0.250, 0.341, -0.211, 0.645, 0.935, -0.316, -0.924]'),
    (2, '[0.443, -0.501, 0.355, -0.771, 0.707, -0.708, -0.185, 0.362]', '[0.443, -0.501, 0.355, -0.771, 0.707, -0.708, -0.185, 0.362]'),
    (3, '[0.716, -0.927, 0.134, 0.052, -0.669, 0.793, -0.634, -0.162]', '[0.716, -0.927, 0.134, 0.052, -0.669, 0.793, -0.634, -0.162]'),
    (4, '[-0.710, 0.330, 0.656, 0.041, -0.990, 0.726, 0.385, -0.958]', '[-0.710, 0.330, 0.656, 0.041, -0.990, 0.726, 0.385, -0.958]');
'''
        test_sql_3 = '''
-- KNN style query
select
  rowid,
  distance
from vec_examples_2
where another_embedding match '[0.890, 0.544, 0.825, 0.961, 0.358, 0.0196, 0.521, 0.175]'
order by distance
limit 2;
'''

        result = conn.execute(test_sql_1).fetchone()
        print(result)

        result = conn.execute(test_sql_2).fetchone()
        print(result)

        result = conn.execute(test_sql_3).fetchone()
        print(result)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
        print("Connection closed.")

    os.remove(db_path)

if __name__ == "__main__":
    main()
