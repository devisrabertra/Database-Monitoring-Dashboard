import pyodbc
import os
import time

def restore_database_sql():
    """
    Melakukan restore database SQL Server menggunakan pyodbc
    """
    try:
        # Konfigurasi koneksi ke SQL Server (HARUS connect ke master database)
        server = 'OGDBATEST01'
        username = 'tes'
        password = 'mydbaccess'
        
        # String koneksi - HARUS ke master database
        conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE=master;UID={username};PWD={password}'
        
        # Membuat koneksi
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Path file backup
        backup_path = r'D:\Dashboard_project\DATA BACKUP\DB_DistributionInventory\Full_DB_DistributionInventory.Bak'
        
        print("Memulai proses restore database...")
        
        # Step 0: Cek file backup ada atau tidak
        if not os.path.exists(backup_path):
            print(f"ERROR: File backup tidak ditemukan di: {backup_path}")
            return False
        
        print(f"File backup ditemukan: {backup_path}")
        
        # Step 1: Set autocommit untuk menghindari transaction error
        conn.autocommit = True
        
        # Step 2: Kill semua proses yang terkait dengan database
        print("Menutup koneksi yang aktif...")
        kill_sql = """
        DECLARE @kill varchar(8000) = '';
        SELECT @kill = @kill + 'kill ' + CONVERT(varchar(5), session_id) + ';'
        FROM sys.dm_exec_sessions
        WHERE database_id = DB_ID('DB_DistributionInventory');
        
        IF @kill != ''
            EXEC(@kill);
        """
        
        try:
            cursor.execute(kill_sql)
            print("Koneksi aktif berhasil ditutup")
        except Exception as e:
            print(f"Peringatan saat kill processes: {e}")
        
        # Step 3: Set database to single user mode dengan rollback immediate
        print("Mengatur database ke single user mode...")
        single_user_sql = """
        IF EXISTS(SELECT * FROM sys.databases WHERE name = 'DB_DistributionInventory')
        BEGIN
            ALTER DATABASE [DB_DistributionInventory] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
        END
        """
        
        try:
            cursor.execute(single_user_sql)
            print("Database berhasil di-set ke single user mode")
        except Exception as e:
            print(f"Peringatan saat set single user mode: {e}")
        
        # Step 4: Restore database
        print("Memulai proses restore...")
        
        # SQL untuk restore database (tanpa MOVE clause dulu)
        restore_sql = f"""
        RESTORE DATABASE [DB_DistributionInventory] 
        FROM DISK = '{backup_path}'
        WITH 
            FILE = 1,
            NOUNLOAD,
            REPLACE,
            STATS = 10
        """
        
        # Eksekusi perintah restore
        print("Eksekusi perintah RESTORE...")
        cursor.execute(restore_sql)
        
        # Tunggu dan tampilkan progress
        print("Restore dalam progress...")
        while True:
            # Process semua result sets
            if not cursor.nextset():
                break
            # Cek jika ada messages
            if hasattr(cursor, 'messages') and cursor.messages:
                for message in cursor.messages:
                    print(f"Progress: {message[1]}")
        
        print("Restore database berhasil!")
        return True
        
    except pyodbc.Error as e:
        print(f"Error saat restore database: {e}")
        # Print detail error
        if hasattr(e, 'args'):
            for i, arg in enumerate(e.args):
                print(f"Detail error {i+1}: {arg}")
        return False
    except Exception as e:
        print(f"Terjadi error: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False
    finally:
        # Tutup koneksi
        if 'conn' in locals():
            conn.close()

# Jalankan fungsi restore
if __name__ == "__main__":
    restore_database_sql()