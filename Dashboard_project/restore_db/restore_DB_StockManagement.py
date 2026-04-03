import pyodbc
import time
import sys

def restore_stock_management_database():
    try:
        server = "OGDBATEST01"
        username = "tes"
        password = "mydbaccess"

        conn = pyodbc.connect(
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server};DATABASE=Dashboard_project;UID={username};PWD={password}",
            autocommit=True
        )
        cursor = conn.cursor()

        print("==============================================")
        print("PROSES RESTORE DB_StockManagement")
        print("Method: Stored Procedure")
        print("==============================================")

        start_time = time.time()

        cursor.execute("EXEC sp_fast_restore_DB_StockManagement")

        while cursor.nextset():
            pass

        end_time = time.time()
        duration = end_time - start_time

        print("==============================================")
        print("RESTORE DB_StockManagement BERHASIL!")
        print(f"DURASI: {duration:.2f} detik ({duration/60:.2f} menit)")
        print("==============================================")

        return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False

    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    success = restore_stock_management_database()
    if success:
        print("STATUS: SUKSES")
        sys.exit(0)
    else:
        print("STATUS: GAGAL")
        sys.exit(1)