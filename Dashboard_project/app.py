from flask import Flask, render_template, request, jsonify
import pyodbc
import time
import subprocess
import os
import pandas as pd
from datetime import datetime, timedelta

# ==================================================
# BACKUP HISTORY IMPORT
# ==================================================
from backup_history import init_backup_history, backup_history_system

app = Flask(__name__)

# ---------------------------------------------
# Koneksi ke SQL Server
# ---------------------------------------------
def GetConnection(connection):
    if connection.lower() == "ogdbatest01":
        server = "OGDBATEST01"
        database = "Dashboard_project"
        user = "tes"
        password = "mydbaccess"
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            f"SERVER={server};DATABASE={database};UID={user};PWD={password}",
            autocommit=True,
            timeout=300
        )
        return conn
    return None

# ---------------------------------------------
# Inisialisasi Backup History System
# ---------------------------------------------
backup_system = init_backup_history(GetConnection)

# ---------------------------------------------
# Ambil nama server
# ---------------------------------------------
def get_server_name():
    conn = GetConnection("ogdbatest01")
    cursor = conn.cursor()
    cursor.execute("SELECT @@SERVERNAME;")
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0]

# ---------------------------------------------
# Ambil Daftar Database (dari sys.databases)
# ---------------------------------------------
def get_database_list():
    query = """
    SELECT name 
    FROM sys.databases 
    WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')
    ORDER BY name;
    """
    conn = GetConnection("ogdbatest01")
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [row[0] for row in rows]

# ---------------------------------------------
# Fungsi untuk menjalankan RESTORE HEADERONLY
# ---------------------------------------------
def run_restore_headeronly(backup_file_path):
    conn = GetConnection("ogdbatest01")
    cursor = conn.cursor()
    query = f"""
    RESTORE HEADERONLY FROM DISK = '{backup_file_path}';
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    columns = [col[0] for col in cursor.description]
    cursor.close()
    conn.close()
    
    # Filter hanya 3 kolom
    filtered = []
    for row in rows:
        row_dict = dict(zip(columns, row))
        filtered.append({
            "ServerName": row_dict.get("ServerName"),
            "DatabaseName": row_dict.get("DatabaseName"),
            "DatabaseCreationDate": row_dict.get("DatabaseCreationDate")
        })
    return filtered

# ---------------------------------------------
# Fungsi untuk menjalankan script Python restore
# ---------------------------------------------
def run_restore_script(script_name):
    """
    Menjalankan script Python untuk restore database
    """
    try:
        # Path ke folder restore_db
        restore_folder = os.path.join(os.path.dirname(__file__), 'restore_db')
        script_path = os.path.join(restore_folder, script_name)
        
        # Pastikan file exists
        if not os.path.exists(script_path):
            return {
                "success": False,
                "message": f"File script {script_name} tidak ditemukan di {restore_folder}"
            }
        
        print(f"🚀 Menjalankan script: {script_path}")
        print(f"⏰ Waktu mulai: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Jalankan script Python
        result = subprocess.run(
            ['python', script_path],
            capture_output=True,
            text=True,
            timeout=1800,
            cwd=restore_folder
        )
        
        print(f"✅ Waktu selesai: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Return code: {result.returncode}")
        print(f"📝 Stdout: {result.stdout}")
        if result.stderr:
            print(f"❌ Stderr: {result.stderr}")
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": f"Restore berhasil via {script_name}",
                "output": result.stdout,
                "error_output": result.stderr
            }
        else:
            return {
                "success": False,
                "message": f"Error saat menjalankan {script_name}",
                "output": result.stdout,
                "error_output": result.stderr
            }
            
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": f"Proses restore timeout (30 menit). Script {script_name} masih berjalan.",
            "output": "",
            "error_output": "Timeout: Process took too long"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error menjalankan script {script_name}: {str(e)}",
            "output": "",
            "error_output": str(e)
        }

# ---------------------------------------------
# Fungsi backup langsung (DIPERBAIKI - TANPA STORED PROCEDURE)
# ---------------------------------------------
def run_backup_direct(database_name, backup_type, custom_date):
    """
    Menjalankan backup langsung menggunakan query SQL tanpa stored procedure
    """
    try:
        conn = GetConnection("ogdbatest01")
        cursor = conn.cursor()
        
        # Format tanggal dari YYYY-MM-DD ke DD_MM_YYYY
        if '-' in custom_date:
            date_obj = datetime.strptime(custom_date, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d_%m_%Y')
        else:
            formatted_date = custom_date.replace('/', '_').replace('-', '_')
        
        # Tentukan folder backup
        backup_folder = r"D:\Backup\FullDiff"
        
        # Pastikan folder ada
        if not os.path.exists(backup_folder):
            os.makedirs(backup_folder, exist_ok=True)
            print(f"📁 Folder backup dibuat: {backup_folder}")
        
        # Tentukan nama file berdasarkan tipe backup
        if backup_type.upper() == 'FULL':
            backup_type_name = 'Full'
            backup_command = f"""
            BACKUP DATABASE [{database_name}] 
            TO DISK = N'{backup_folder}\\{backup_type_name}_{database_name}_{formatted_date}.BAK'
            WITH NOFORMAT, INIT, NAME = N'{database_name}-Full Database Backup', 
            SKIP, NOREWIND, NOUNLOAD, STATS = 10
            """
        elif backup_type.upper() == 'DIFF':
            backup_type_name = 'DIFF'
            backup_command = f"""
            BACKUP DATABASE [{database_name}] 
            TO DISK = N'{backup_folder}\\{backup_type_name}_{database_name}_{formatted_date}.BAK'
            WITH DIFFERENTIAL, NOFORMAT, INIT, NAME = N'{database_name}-Differential Database Backup', 
            SKIP, NOREWIND, NOUNLOAD, STATS = 10
            """
        elif backup_type.upper() == 'LOG':
            backup_type_name = 'Log'
            backup_command = f"""
            BACKUP LOG [{database_name}] 
            TO DISK = N'{backup_folder}\\{backup_type_name}_{database_name}_{formatted_date}.BAK'
            WITH NOFORMAT, INIT, NAME = N'{database_name}-Log Backup', 
            SKIP, NOREWIND, NOUNLOAD, STATS = 10
            """
        else:
            return {
                "success": False,
                "message": f"Tipe backup tidak valid: {backup_type}"
            }
        
        print(f"🔧 Menjalankan backup langsung:")
        print(f"   Database: {database_name}")
        print(f"   Type: {backup_type}")
        print(f"   Tanggal asli: {custom_date}")
        print(f"   Tanggal format: {formatted_date}")
        print(f"   File: {backup_folder}\\{backup_type_name}_{database_name}_{formatted_date}.BAK")
        
        # Jalankan backup
        cursor.execute(backup_command)
        
        # Tunggu sebentar agar file selesai ditulis
        time.sleep(3)
        
        # Cek file backup
        expected_filepath = f"{backup_folder}\\{backup_type_name}_{database_name}_{formatted_date}.BAK"
        
        # Jika file tidak ditemukan, coba cari dengan pola yang mirip
        file_created = os.path.exists(expected_filepath)
        if not file_created:
            print(f"⚠️ File tidak ditemukan di {expected_filepath}, mencoba mencari...")
            try:
                files = os.listdir(backup_folder)
                for file in files:
                    if database_name in file and backup_type_name in file and formatted_date in file:
                        expected_filepath = os.path.join(backup_folder, file)
                        file_created = True
                        print(f"✅ File ditemukan: {file}")
                        break
            except Exception as e:
                print(f"Error mencari file: {e}")
        
        cursor.close()
        conn.close()
        
        if file_created:
            file_size = os.path.getsize(expected_filepath)
            file_size_mb = file_size / (1024 * 1024)
            
            if file_size > 0:
                return {
                    "success": True,
                    "message": f"✅ Backup {backup_type} untuk database {database_name} BERHASIL!",
                    "database_name": database_name,
                    "backup_type": backup_type,
                    "custom_date": formatted_date,
                    "backup_file": expected_filepath,
                    "file_size": f"{file_size_mb:.2f} MB",
                    "output": f"Backup completed successfully. File size: {file_size_mb:.2f} MB"
                }
            else:
                return {
                    "success": False,
                    "message": f"⚠️ File backup dibuat tetapi kosong (0 bytes). Backup mungkin gagal.",
                    "database_name": database_name,
                    "backup_type": backup_type,
                    "custom_date": formatted_date,
                    "expected_file": expected_filepath,
                    "output": "Backup file created but empty"
                }
        else:
            return {
                "success": False,
                "message": f"❌ Backup GAGAL. File backup tidak ditemukan di {backup_folder}",
                "database_name": database_name,
                "backup_type": backup_type,
                "custom_date": formatted_date,
                "expected_file": expected_filepath,
                "output": f"Expected file: {backup_type_name}_{database_name}_{formatted_date}.BAK not found"
            }
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error saat backup: {error_msg}")
        import traceback
        traceback.print_exc()
        
        return {
            "success": False,
            "message": f"Error saat backup: {error_msg}",
            "database_name": database_name,
            "backup_type": backup_type,
            "custom_date": custom_date,
            "error": error_msg
        }

# ---------------------------------------------
# HOME
# ---------------------------------------------
@app.route("/")
def home():
    server_name = get_server_name()
    backup_summary = backup_system.get_backup_summary(days_back=33)
    
    data = {
        "title": "Dashboard Monitoring",
        "server_status": [{"server": server_name, "status": "Database"}],
        "databases": [],
        "show_validation_box": False,
        "show_restore_box": False,
        "show_backup_box": False,
        "restore_header": [],
        "show_databases": False,
        "show_history": False,
        "show_history_results": False,
        "backup_history": None,
        "backup_databases": [],
        "restore_result": None,
        "backup_summary": backup_summary
    }
    return render_template("index.html", data=data)

# ---------------------------------------------
# DATABASE LIST
# ---------------------------------------------
@app.route("/get_databases", methods=["POST"])
def show_databases():
    database_list = get_database_list()
    server_name = get_server_name()
    backup_summary = backup_system.get_backup_summary(days_back=33)
    
    data = {
        "title": "Dashboard Monitoring",
        "server_status": [{"server": server_name, "status": "Database"}],
        "databases": database_list,
        "show_validation_box": False,
        "show_restore_box": False,
        "show_backup_box": False,
        "restore_header": [],
        "show_databases": True,
        "show_history": False,
        "show_history_results": False,
        "backup_history": None,
        "backup_databases": [],
        "restore_result": None,
        "backup_summary": backup_summary
    }
    return render_template("index.html", data=data)

# ---------------------------------------------
# HISTORY BACKUP - LANGSUNG TAMPILKAN DATA
# ---------------------------------------------
@app.route("/history_backup", methods=["POST"])
def history_backup():
    server_name = get_server_name()
    
    print("🔍 Mengambil backup history...")
    
    # Ambil daftar database dari backup history
    backup_databases = backup_system.get_backup_databases(days_back=33)
    
    # Ambil ringkasan backup
    backup_summary = backup_system.get_backup_summary(days_back=33)
    
    # LANGSUNG AMBIL DATA HISTORY (tanpa filter)
    history_result = backup_system.get_backup_history(
        database_name=None,
        backup_type=None,
        limit=1000,
        days_back=33
    )
    
    print(f"📊 Hasil: {history_result.get('count', 0)} records, Success: {history_result.get('success', False)}")
    
    # Ambil total count
    total_count = backup_system.get_backup_count(None, None, days_back=33)
    
    data = {
        "title": "Dashboard Monitoring",
        "server_status": [{"server": server_name, "status": "Database"}],
        "databases": [],
        "show_validation_box": False,
        "show_restore_box": False,
        "show_backup_box": False,
        "restore_header": [],
        "show_databases": False,
        "show_history": True,
        "show_history_results": True,
        "backup_history": history_result,
        "backup_databases": backup_databases,
        "restore_result": None,
        "backup_summary": backup_summary,
        "total_count": total_count,
        "selected_database": "all",
        "selected_backup_type": "all"
    }
    return render_template("index.html", data=data)

# ---------------------------------------------
# PROSES HISTORY BACKUP (DENGAN FILTER)
# ---------------------------------------------
@app.route("/proses_history_backup", methods=["POST"])
def proses_history_backup():
    database_name = request.form.get("databaseSelect")
    backup_type = request.form.get("backupTypeSelect")
    limit = int(request.form.get("limit", 1000))
    days_back = int(request.form.get("days_back", 33))
    
    server_name = get_server_name()
    
    print(f"🔍 Filtering backup history - DB: {database_name}, Type: {backup_type}, Limit: {limit}")
    
    # Ambil daftar database dari backup history
    backup_databases = backup_system.get_backup_databases(days_back=days_back)
    
    # Ambil data history backup dengan filter
    history_result = backup_system.get_backup_history(
        database_name=database_name, 
        backup_type=backup_type, 
        limit=limit,
        days_back=days_back
    )
    
    print(f"📊 Hasil filter: {history_result.get('count', 0)} records")
    
    # Ambil total count untuk informasi
    total_count = backup_system.get_backup_count(database_name, backup_type, days_back=days_back)
    
    # Ambil ringkasan backup
    backup_summary = backup_system.get_backup_summary(days_back=days_back)
    
    data = {
        "title": "Dashboard Monitoring",
        "server_status": [{"server": server_name, "status": "Database"}],
        "databases": [],
        "show_validation_box": False,
        "show_restore_box": False,
        "show_backup_box": False,
        "restore_header": [],
        "show_databases": False,
        "show_history": True,
        "show_history_results": True,
        "backup_history": history_result,
        "backup_databases": backup_databases,
        "selected_database": database_name,
        "selected_backup_type": backup_type,
        "total_count": total_count,
        "restore_result": None,
        "backup_summary": backup_summary
    }
    return render_template("index.html", data=data)

# ---------------------------------------------
# BACKUP DATABASE PAGE
# ---------------------------------------------
@app.route("/backup_database_page", methods=["POST"])
def backup_database_page():
    server_name = get_server_name()
    backup_summary = backup_system.get_backup_summary(days_back=33)
    
    # Ambil daftar database dari server
    database_list = get_database_list()
    
    # Data untuk tanggal (hari ini dalam format YYYY-MM-DD untuk date picker)
    today = datetime.now()
    current_date = today.strftime('%Y-%m-%d')
    
    # Cek folder backup
    backup_folder = r"D:\Backup\FullDiff"
    folder_exists = os.path.exists(backup_folder)
    folder_writable = os.access(backup_folder, os.W_OK) if folder_exists else False
    
    data = {
        "title": "Dashboard Monitoring - Backup Database",
        "server_status": [{"server": server_name, "status": "Database"}],
        "databases": [],
        "show_validation_box": False,
        "show_restore_box": False,
        "show_backup_box": True,
        "restore_header": [],
        "show_databases": False,
        "show_history": False,
        "show_history_results": False,
        "backup_history": None,
        "backup_databases": [],
        "restore_result": None,
        "backup_summary": backup_summary,
        "database_list": database_list,
        "current_date": current_date,
        "backup_folder": backup_folder,
        "folder_exists": folder_exists,
        "folder_writable": folder_writable
    }
    return render_template("index.html", data=data)

# ---------------------------------------------
# PROSES BACKUP DATABASE (MENGGUNAKAN FUNGSI LANGSUNG)
# ---------------------------------------------
@app.route("/proses_backup", methods=["POST"])
def proses_backup():
    database_name = request.form.get("databaseSelect")
    backup_type = request.form.get("backupTypeSelect")
    custom_date = request.form.get("dateSelect")  # Format: YYYY-MM-DD dari date picker
    
    server_name = get_server_name()
    
    # Validasi input
    if not database_name or not backup_type or not custom_date:
        backup_summary = backup_system.get_backup_summary(days_back=33)
        database_list = get_database_list()
        
        backup_folder = r"D:\Backup\FullDiff"
        folder_exists = os.path.exists(backup_folder)
        folder_writable = os.access(backup_folder, os.W_OK) if folder_exists else False
        
        data = {
            "title": "Dashboard Monitoring - Backup Database",
            "server_status": [{"server": server_name, "status": "Database"}],
            "databases": [],
            "show_validation_box": False,
            "show_restore_box": False,
            "show_backup_box": True,
            "restore_header": [],
            "show_databases": False,
            "show_history": False,
            "show_history_results": False,
            "backup_history": None,
            "backup_databases": [],
            "restore_result": None,
            "backup_summary": backup_summary,
            "database_list": database_list,
            "current_date": datetime.now().strftime('%Y-%m-%d'),
            "backup_folder": backup_folder,
            "folder_exists": folder_exists,
            "folder_writable": folder_writable,
            "error_message": "Harap lengkapi semua pilihan backup!",
            "backup_result": None
        }
        return render_template("index.html", data=data)
    
    print(f"🔄 Memulai proses backup untuk database: {database_name}")
    print(f"📦 Tipe Backup: {backup_type}")
    print(f"📅 Tanggal: {custom_date}")
    
    # Gunakan fungsi backup langsung
    backup_result = run_backup_direct(database_name, backup_type, custom_date)
    
    # Ambil daftar database untuk form
    database_list = get_database_list()
    
    backup_summary = backup_system.get_backup_summary(days_back=33)
    
    backup_folder = r"D:\Backup\FullDiff"
    folder_exists = os.path.exists(backup_folder)
    folder_writable = os.access(backup_folder, os.W_OK) if folder_exists else False
    
    data = {
        "title": "Dashboard Monitoring - Backup Database",
        "server_status": [{"server": server_name, "status": "Database"}],
        "databases": [],
        "show_validation_box": False,
        "show_restore_box": False,
        "show_backup_box": True,
        "restore_header": [],
        "show_databases": False,
        "show_history": False,
        "show_history_results": False,
        "backup_history": None,
        "backup_databases": [],
        "restore_result": None,
        "backup_summary": backup_summary,
        "database_list": database_list,
        "backup_result": backup_result,
        "backup_folder": backup_folder,
        "folder_exists": folder_exists,
        "folder_writable": folder_writable,
        "selected_database_backup": database_name,
        "selected_backup_type_backup": backup_type,
        "selected_date_backup": custom_date,
        "current_date": datetime.now().strftime('%Y-%m-%d')
    }
    return render_template("index.html", data=data)

# ---------------------------------------------
# VALIDASI BAK
# ---------------------------------------------
@app.route("/validasi_bak", methods=["POST"])
def validasi_bak():
    server_name = get_server_name()
    backup_summary = backup_system.get_backup_summary(days_back=33)
    
    data = {
        "title": "Dashboard Monitoring",
        "server_status": [{"server": server_name, "status": "Database"}],
        "databases": [],
        "show_validation_box": True,
        "show_restore_box": False,
        "show_backup_box": False,
        "restore_header": [],
        "show_databases": False,
        "show_history": False,
        "show_history_results": False,
        "backup_history": None,
        "backup_databases": [],
        "restore_result": None,
        "backup_summary": backup_summary
    }
    return render_template("index.html", data=data)

# ---------------------------------------------
# RESTORE DATABASE
# ---------------------------------------------
@app.route("/restore_database", methods=["POST"])
def restore_database():
    server_name = get_server_name()
    backup_summary = backup_system.get_backup_summary(days_back=33)
    
    data = {
        "title": "Dashboard Monitoring",
        "server_status": [{"server": server_name, "status": "Database"}],
        "databases": [],
        "show_validation_box": False,
        "show_restore_box": True,
        "show_backup_box": False,
        "restore_header": [],
        "show_databases": False,
        "show_history": False,
        "show_history_results": False,
        "backup_history": None,
        "backup_databases": [],
        "restore_result": None,
        "backup_summary": backup_summary
    }
    return render_template("index.html", data=data)

# ---------------------------------------------
# PROSES VALIDASI
# ---------------------------------------------
@app.route("/proses_validasi", methods=["POST"])
def proses_validasi():
    pilihan = request.form.get("validationSelect")
    server_name = get_server_name()
    
    backup_files = {
        "1": "D:\\Dashboard_project\\DATA BACKUP\\DB_DistributionInventory\\Full_DB_DistributionInventory.Bak",
        "2": "D:\\Dashboard_project\\DATA BACKUP\\DB_LogisticsInventory\\Full_DB_LogisticsInventory.Bak",
        "3": "D:\\Dashboard_project\\DATA BACKUP\\DB_StockManagement\\Full_DB_StockManagement.Bak",
        "4": "D:\\Dashboard_project\\DATA BACKUP\\DB_Warehouse\\Full_DB_Warehouse.Bak",
        "5": "D:\\Dashboard_project\\DATA BACKUP\\DB_InventoriBarang\\Full_DB_InventoriBarang.Bak"
    }
    
    backup_summary = backup_system.get_backup_summary(days_back=33)
    
    if pilihan in backup_files:
        backup_file_path = backup_files[pilihan]
        try:
            filtered_results = run_restore_headeronly(backup_file_path)
            data = {
                "title": "Dashboard Monitoring",
                "server_status": [{"server": server_name, "status": "Database"}],
                "databases": [],
                "show_validation_box": True,
                "show_restore_box": False,
                "show_backup_box": False,
                "restore_header": filtered_results,
                "show_databases": False,
                "show_history": False,
                "show_history_results": False,
                "backup_history": None,
                "backup_databases": [],
                "backup_file_used": backup_file_path,
                "restore_result": None,
                "backup_summary": backup_summary
            }
        except Exception as e:
            data = {
                "title": "Dashboard Monitoring",
                "server_status": [{"server": server_name, "status": "Database"}],
                "databases": [],
                "show_validation_box": True,
                "show_restore_box": False,
                "show_backup_box": False,
                "restore_header": [],
                "show_databases": False,
                "show_history": False,
                "show_history_results": False,
                "backup_history": None,
                "backup_databases": [],
                "error_message": f"Error: {str(e)}",
                "restore_result": None,
                "backup_summary": backup_summary
            }
    else:
        data = {
            "title": "Dashboard Monitoring",
            "server_status": [{"server": server_name, "status": "Database"}],
            "databases": [],
            "show_validation_box": True,
            "show_restore_box": False,
            "show_backup_box": False,
            "restore_header": [],
            "show_databases": False,
            "show_history": False,
            "show_history_results": False,
            "backup_history": None,
            "backup_databases": [],
            "restore_result": None,
            "backup_summary": backup_summary
        }
    
    return render_template("index.html", data=data)

# ---------------------------------------------
# PROSES RESTORE
# ---------------------------------------------
@app.route("/proses_restore", methods=["POST"])
def proses_restore():
    pilihan = request.form.get("restoreSelect")
    server_name = get_server_name()
    
    restore_mapping = {
        "1": {
            "name": "DB_DistributionInventory",
            "script": "restore_DB_DistributionInventory.py",
            "database_name": "DB_DistributionInventory"
        },
        "2": {
            "name": "DB_LogisticsInventory", 
            "script": "restore_DB_LogisticsInventory.py",
            "database_name": "DB_LogisticsInventory"
        },
        "3": {
            "name": "DB_StockManagement",
            "script": "restore_DB_StockManagement.py", 
            "database_name": "DB_StockManagement"
        },
        "4": {
            "name": "DB_Warehouse",
            "script": "restore_DB_Warehouse.py",
            "database_name": "DB_Warehouse"
        },
        "5": {
            "name": "DB_InventoriBarang",
            "script": "restore_DB_InventoriBarang.py",
            "database_name": "DB_InventoriBarang"
        }
    }
    
    backup_summary = backup_system.get_backup_summary(days_back=33)
    
    if pilihan in restore_mapping:
        restore_info = restore_mapping[pilihan]
        print(f"🎯 Memulai proses restore untuk: {restore_info['name']}")
        print(f"📜 Menggunakan script: {restore_info['script']}")
        
        restore_result = run_restore_script(restore_info["script"])
        
        data = {
            "title": "Dashboard Monitoring",
            "server_status": [{"server": server_name, "status": "Database"}],
            "databases": [],
            "show_validation_box": False,
            "show_restore_box": True,
            "show_backup_box": False,
            "restore_header": [],
            "show_databases": False,
            "show_history": False,
            "show_history_results": False,
            "backup_history": None,
            "backup_databases": [],
            "restore_result": {
                "success": restore_result["success"],
                "message": restore_result["message"],
                "database_name": restore_info["name"],
                "script_used": restore_info["script"],
                "output": restore_result.get("output", ""),
                "error_output": restore_result.get("error_output", "")
            },
            "backup_summary": backup_summary
        }
    else:
        data = {
            "title": "Dashboard Monitoring",
            "server_status": [{"server": server_name, "status": "Database"}],
            "databases": [],
            "show_validation_box": False,
            "show_restore_box": True,
            "show_backup_box": False,
            "restore_header": [],
            "show_databases": False,
            "show_history": False,
            "show_history_results": False,
            "backup_history": None,
            "backup_databases": [],
            "restore_result": None,
            "backup_summary": backup_summary
        }
    
    return render_template("index.html", data=data)

# ---------------------------------------------
# ERROR HANDLERS
# ---------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    backup_summary = backup_system.get_backup_summary(days_back=33)
    return render_template('index.html', data={
        "title": "Dashboard Monitoring - Page Not Found",
        "server_status": [{"server": get_server_name(), "status": "Database"}],
        "databases": [],
        "show_validation_box": False,
        "show_restore_box": False,
        "show_backup_box": False,
        "restore_header": [],
        "show_databases": False,
        "show_history": False,
        "show_history_results": False,
        "backup_history": None,
        "backup_databases": [],
        "restore_result": None,
        "error_message": "Halaman tidak ditemukan.",
        "backup_summary": backup_summary
    }), 404

@app.errorhandler(500)
def internal_server_error(e):
    backup_summary = backup_system.get_backup_summary(days_back=33)
    return render_template('index.html', data={
        "title": "Dashboard Monitoring - Server Error",
        "server_status": [{"server": get_server_name(), "status": "Database"}],
        "databases": [],
        "show_validation_box": False,
        "show_restore_box": False,
        "show_backup_box": False,
        "restore_header": [],
        "show_databases": False,
        "show_history": False,
        "show_history_results": False,
        "backup_history": None,
        "backup_databases": [],
        "restore_result": None,
        "error_message": "Terjadi kesalahan internal server.",
        "backup_summary": backup_summary
    }), 500

# ---------------------------------------------
# RUN
# ---------------------------------------------
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Dashboard Monitoring Server Starting...")
    print("🖥️ Server: OGDBATEST01")
    print("🗄️ Database: Dashboard_project")
    print(f"⏰ Start Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Cek folder backup
    backup_folder = r"D:\Backup\FullDiff"
    print(f"\n📁 Checking backup folder: {backup_folder}")
    if os.path.exists(backup_folder):
        print(f"   ✅ Folder exists")
        if os.access(backup_folder, os.W_OK):
            print(f"   ✅ Folder is writable")
        else:
            print(f"   ❌ Folder is NOT writable! Please check permissions.")
    else:
        print(f"   ❌ Folder does NOT exist!")
        print(f"   📝 Creating folder: {backup_folder}")
        try:
            os.makedirs(backup_folder, exist_ok=True)
            print(f"   ✅ Folder created successfully!")
        except Exception as e:
            print(f"   ❌ Failed to create folder: {e}")
    
    restore_folder = os.path.join(os.path.dirname(__file__), 'restore_db')
    if os.path.exists(restore_folder):
        print(f"\n✅ Folder restore_db ditemukan: {restore_folder}")
        python_files = [f for f in os.listdir(restore_folder) if f.endswith('.py')]
        print(f"✅ Script restore yang tersedia: {python_files}")
    else:
        print(f"\n❌ Folder restore_db tidak ditemukan: {restore_folder}")
    
    print("\n📊 Testing Backup History System...")
    test_summary = backup_system.get_backup_summary(days_back=7)
    print(f"   Total backups (7 days): {test_summary.get('total_backups', 0)}")
    print(f"   Total databases: {test_summary.get('total_databases', 0)}")
    
    print("\n" + "=" * 50)
    print("🌐 Server running at: http://0.0.0.0:5000")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)