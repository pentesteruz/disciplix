import os
import sys
from sqlalchemy import create_engine, MetaData, Table, Column, select

def backup(pg_url, sqlite_path):
    print(f"Connecting to PostgreSQL: {pg_url}...")
    try:
        pg_engine = create_engine(pg_url)
    except Exception as e:
        print(f"Failed to create engine for PostgreSQL: {e}")
        sys.exit(1)
        
    sqlite_url = f"sqlite:///{os.path.abspath(sqlite_path)}"
    print(f"Connecting to SQLite: {sqlite_url}...")
    try:
        sqlite_engine = create_engine(sqlite_url)
    except Exception as e:
        print(f"Failed to create engine for SQLite: {e}")
        sys.exit(1)
        
    pg_meta = MetaData()
    try:
        pg_meta.reflect(bind=pg_engine)
    except Exception as e:
        print(f"Failed to reflect PostgreSQL database: {e}")
        sys.exit(1)
        
    print(f"Reflected {len(pg_meta.tables)} tables from PostgreSQL.")
    
    # Create directory for SQLite file
    os.makedirs(os.path.dirname(os.path.abspath(sqlite_path)), exist_ok=True)
    
    for table_name, pg_table in pg_meta.tables.items():
        print(f"\nProcessing table: {table_name}...")
        
        # Clone table structure for SQLite (without foreign keys to avoid creation order constraints)
        lite_meta = MetaData()
        lite_columns = []
        for col in pg_table.columns:
            new_col = Column(
                col.name, 
                col.type, 
                primary_key=col.primary_key, 
                nullable=col.nullable, 
                default=col.default
            )
            lite_columns.append(new_col)
            
        lite_table = Table(table_name, lite_meta, *lite_columns)
        
        try:
            # Recreate table in SQLite
            lite_meta.create_all(sqlite_engine)
        except Exception as e:
            print(f"Failed to create table {table_name} in SQLite: {e}")
            continue
            
        # Fetch rows from Postgres
        try:
            with pg_engine.connect() as pg_conn:
                rows = pg_conn.execute(select(pg_table)).fetchall()
        except Exception as e:
            print(f"Failed to fetch data from table {table_name}: {e}")
            continue
            
        if rows:
            try:
                # Convert rows to list of dicts
                data = [dict(row._mapping) for row in rows]
                with sqlite_engine.connect() as lite_conn:
                    lite_conn.execute(lite_table.insert(), data)
                    lite_conn.commit()
                print(f"Successfully copied {len(rows)} rows for table {table_name}.")
            except Exception as e:
                print(f"Failed to write data into SQLite table {table_name}: {e}")
        else:
            print(f"Table {table_name} is empty.")

    print("\nDatabase backup complete!")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python db_backup.py <pg_url> <sqlite_path>")
        sys.exit(1)
    backup(sys.argv[1], sys.argv[2])
