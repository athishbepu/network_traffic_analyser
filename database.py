import mysql.connector
from config import DB_CONFIG

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

def insert_packet(source_ip, destination_ip, source_mac, destination_mac, protocol, port, packet_size, traffic_type):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        print("inserting values")
        query = """INSERT INTO packets (source_ip, destination_ip, source_mac, destination_mac, protocol, port, packet_size, traffic_type) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
        print(query)
        cursor.execute(query, (source_ip, destination_ip, source_mac, destination_mac, protocol, port, packet_size, traffic_type))
        conn.commit()
        cursor.close()
        conn.close()