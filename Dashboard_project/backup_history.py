# ==================================================
# BACKUP HISTORY MODULE
# File: backup_history.py
# Lokasi: D:\DASHBOARD_PROJECT\backup_history.py
# ==================================================
import pyodbc
import pandas as pd
from datetime import datetime

class BackupHistory:
    """
    Class untuk mengelola backup history dari SQL Server
    """
    
    def __init__(self, connection_string_func):
        """
        Inisialisasi dengan fungsi koneksi database
        Args:
            connection_string_func: Fungsi yang mengembalikan koneksi database
        """
        self.get_connection = connection_string_func
    
    def get_backup_history(self, database_name=None, backup_type=None, limit=1000, days_back=33):
        """
        Mengambil history backup dengan filter dan limit
        
        Args:
            database_name: Nama database (optional)
            backup_type: Tipe backup (Database/Incremental/Log) (optional)
            limit: Jumlah maksimal records (default 1000)
            days_back: Jumlah hari kebelakang (default 33)
        
        Returns:
            Dictionary dengan data backup history
        """
        try:
            # Query utama sesuai permintaan
            query = """
            SELECT TOP ({}) 
                CONVERT(CHAR(100), SERVERPROPERTY('Servername')) AS Server, 
                bs.database_name, 
                bs.backup_start_date, 
                bs.backup_finish_date, 
                bs.expiration_date, 
                CASE bs.type 
                    WHEN 'D' THEN 'Database' 
                    WHEN 'I' THEN 'Incremental' 
                    WHEN 'L' THEN 'Log' 
                END AS backup_type, 
                bs.backup_size, 
                bmf.logical_device_name, 
                bmf.physical_device_name, 
                bs.name AS backupset_name, 
                bs.description 
            FROM msdb.dbo.backupmediafamily bmf
            INNER JOIN msdb.dbo.backupset bs 
                ON bmf.media_set_id = bs.media_set_id 
            WHERE (CONVERT(datetime, bs.backup_start_date, 102) >= GETDATE() - ?)
            """
            
            params = [limit, days_back]
            
            # Filter berdasarkan database name
            if database_name and database_name != "all" and database_name != "None":
                query += " AND bs.database_name = ?"
                params.append(database_name)
            
            # Filter berdasarkan backup type
            if backup_type and backup_type != "all" and backup_type != "None":
                # Konversi backup type ke format SQL
                type_mapping = {
                    "database": "D",
                    "incremental": "I",
                    "log": "L",
                    "Database": "D",
                    "Incremental": "I",
                    "Log": "L"
                }
                if backup_type.lower() in type_mapping:
                    query += " AND bs.type = ?"
                    params.append(type_mapping[backup_type.lower()])
            
            query += " ORDER BY bs.backup_finish_date DESC"
            
            # Format query dengan limit
            final_query = query.format(limit)
            
            # Eksekusi query
            conn = self.get_connection("ogdbatest01")
            
            # Hapus parameter limit dari params untuk pandas (sudah di format ke query)
            pandas_params = params[1:]  # Skip limit parameter
            df = pd.read_sql(final_query, conn, params=pandas_params)
            conn.close()
            
            # Konversi DataFrame ke list of dictionaries
            backup_history = df.to_dict('records')
            
            # Konversi datetime objects ke string untuk JSON serialization
            for record in backup_history:
                for key, value in record.items():
                    if isinstance(value, datetime):
                        record[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                    elif hasattr(value, 'strftime'):  # Handle other date types
                        record[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            
            return {
                "success": True,
                "data": backup_history,
                "count": len(backup_history),
                "limit": limit,
                "days_back": days_back,
                "limit_reached": len(backup_history) == limit
            }
            
        except Exception as e:
            print(f"❌ Error in get_backup_history: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "count": 0
            }
    
    def get_backup_databases(self, days_back=33):
        """
        Mengambil daftar unik database yang memiliki backup history
        
        Args:
            days_back: Jumlah hari kebelakang (default 33)
        
        Returns:
            List of database names
        """
        try:
            query = """
            SELECT DISTINCT bs.database_name
            FROM msdb.dbo.backupmediafamily bmf
            INNER JOIN msdb.dbo.backupset bs 
                ON bmf.media_set_id = bs.media_set_id 
            WHERE (CONVERT(datetime, bs.backup_start_date, 102) >= GETDATE() - ?)
            ORDER BY bs.database_name
            """
            
            conn = self.get_connection("ogdbatest01")
            cursor = conn.cursor()
            cursor.execute(query, [days_back])
            rows = cursor.fetchall()
            conn.close()
            
            databases = [row[0] for row in rows]
            return databases
            
        except Exception as e:
            print(f"Error getting backup databases: {str(e)}")
            return []
    
    def get_backup_count(self, database_name=None, backup_type=None, days_back=33):
        """
        Mengambil jumlah total backup records untuk informasi
        
        Args:
            database_name: Nama database (optional)
            backup_type: Tipe backup (optional)
            days_back: Jumlah hari kebelakang (default 33)
        
        Returns:
            Integer jumlah records
        """
        try:
            query = """
            SELECT COUNT(*) as total_count
            FROM msdb.dbo.backupmediafamily bmf
            INNER JOIN msdb.dbo.backupset bs 
                ON bmf.media_set_id = bs.media_set_id 
            WHERE (CONVERT(datetime, bs.backup_start_date, 102) >= GETDATE() - ?)
            """
            
            params = [days_back]
            
            if database_name and database_name != "all" and database_name != "None":
                query += " AND bs.database_name = ?"
                params.append(database_name)
            
            if backup_type and backup_type != "all" and backup_type != "None":
                type_mapping = {
                    "database": "D",
                    "incremental": "I",
                    "log": "L",
                    "Database": "D",
                    "Incremental": "I",
                    "Log": "L"
                }
                if backup_type.lower() in type_mapping:
                    query += " AND bs.type = ?"
                    params.append(type_mapping[backup_type.lower()])
            
            conn = self.get_connection("ogdbatest01")
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            conn.close()
            
            return row[0] if row else 0
            
        except Exception as e:
            print(f"Error getting backup count: {str(e)}")
            return 0
    
    def get_backup_summary(self, days_back=33):
        """
        Mendapatkan ringkasan backup untuk dashboard
        
        Returns:
            Dictionary dengan data ringkasan
        """
        try:
            query = """
            SELECT 
                COUNT(*) as total_backups,
                COUNT(DISTINCT bs.database_name) as total_databases,
                SUM(CASE WHEN bs.type = 'D' THEN 1 ELSE 0 END) as full_backups,
                SUM(CASE WHEN bs.type = 'I' THEN 1 ELSE 0 END) as incremental_backups,
                SUM(CASE WHEN bs.type = 'L' THEN 1 ELSE 0 END) as log_backups,
                MAX(bs.backup_finish_date) as last_backup_date
            FROM msdb.dbo.backupmediafamily bmf
            INNER JOIN msdb.dbo.backupset bs 
                ON bmf.media_set_id = bs.media_set_id 
            WHERE (CONVERT(datetime, bs.backup_start_date, 102) >= GETDATE() - ?)
            """
            
            conn = self.get_connection("ogdbatest01")
            df = pd.read_sql(query, conn, params=[days_back])
            conn.close()
            
            if not df.empty:
                summary = df.iloc[0].to_dict()
                # Konversi datetime
                if summary.get('last_backup_date') and hasattr(summary['last_backup_date'], 'strftime'):
                    summary['last_backup_date'] = summary['last_backup_date'].strftime('%Y-%m-%d %H:%M:%S')
                return summary
            else:
                return {
                    "total_backups": 0,
                    "total_databases": 0,
                    "full_backups": 0,
                    "incremental_backups": 0,
                    "log_backups": 0,
                    "last_backup_date": None
                }
                
        except Exception as e:
            print(f"Error getting backup summary: {str(e)}")
            return {
                "total_backups": 0,
                "total_databases": 0,
                "full_backups": 0,
                "incremental_backups": 0,
                "log_backups": 0,
                "last_backup_date": None
            }


# Global instance (akan diinisialisasi di app.py)
backup_history_system = None


def init_backup_history(get_connection_func):
    """
    Inisialisasi global backup history system
    """
    global backup_history_system
    backup_history_system = BackupHistory(get_connection_func)
    return backup_history_system