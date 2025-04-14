from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO
from scapy.all import sniff, IP, TCP, UDP, Ether
import mysql.connector
import threading
import time
from config import DB_CONFIG
from database import insert_packet

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")  # Enable WebSockets


# Function to convert datetime objects to strings for JSON serialization
def convert_datetime(data):
    for row in data:
        for key, value in row.items():
            if hasattr(value, "isoformat"):  # Convert datetime objects
                row[key] = value.isoformat()
    return data


# Fetch all packets (past + new)
def fetch_all_packets():
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)

    query = "SELECT * FROM packets ORDER BY timestamp DESC"
    cursor.execute(query)
    packets = cursor.fetchall()

    cursor.close()
    connection.close()
    return convert_datetime(packets)


# Fetch all network insights (past + new)
def fetch_all_insights():
    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor(dictionary=True)

    query = "SELECT * FROM network_insights ORDER BY detected_at DESC"
    cursor.execute(query)
    insights = cursor.fetchall()

    cursor.close()
    connection.close()
    return convert_datetime(insights)


# Insert new insights and emit real-time updates
def save_insights(insights):
    if not insights:
        return

    connection = mysql.connector.connect(**DB_CONFIG)
    cursor = connection.cursor()

    query = "INSERT INTO network_insights (insight, recommendation) VALUES (%s, %s)"
    for insight in insights:
        cursor.execute(query, (insight["insight"], insight["recommendation"]))

    connection.commit()
    cursor.close()
    connection.close()

    print(f"Inserted {len(insights)} new insights.")

    # Send **past and new** insights to UI in real-time
    all_insights = fetch_all_insights()
    socketio.emit("update_insights", all_insights)


# Analyze network traffic (Runs every 10 seconds)
def analyze_traffic():
    while True:
        print("Fetching recent network traffic...")
        packets = fetch_all_packets()

        if packets:
            print(f"Analyzing {len(packets)} packets...")

            insights = []
            ip_count = {}
            port_count = {}
            threat_count = 0
            suspicious_count = 0

            for packet in packets:
                src_ip = packet["source_ip"]
                protocol = packet["protocol"]
                port = packet["port"]
                traffic_type = packet["traffic_type"]

                ip_count[src_ip] = ip_count.get(src_ip, 0) + 1
                port_count[port] = port_count.get(port, 0) + 1

                if traffic_type == "Threat":
                    threat_count += 1
                elif traffic_type == "Suspicious":
                    suspicious_count += 1

            # Detect high traffic from a single IP
            for ip, count in ip_count.items():
                if count > 20:
                    insights.append({
                        "insight": f"High traffic detected from {ip} ({count} packets).",
                        "recommendation": "Investigate potential attack or excessive usage."
                    })

            # Detect frequent access to uncommon ports
            for port, count in port_count.items():
                if port not in [80, 443, 22, 53] and count > 5:
                    insights.append({
                        "insight": f"Unusual activity detected on port {port} ({count} times).",
                        "recommendation": "Monitor for possible anomalies."
                    })

            # Alert on excessive threat or suspicious traffic
            if threat_count > 3:
                insights.append({
                    "insight": f"Multiple threat-level packets detected ({threat_count}).",
                    "recommendation": "Immediate investigation required."
                })

            if suspicious_count > 5:
                insights.append({
                    "insight": f"High suspicious traffic detected ({suspicious_count} packets).",
                    "recommendation": "Monitor for possible DNS tunneling or attacks."
                })

            # Save insights and send updates in real time
            save_insights(insights)
        else:
            print("No new packets found.")

        time.sleep(10)


# Capture packets, insert into MySQL, and send real-time updates
def process_packet(packet):
    print("Packet Captured:", packet.summary())  # Prints a summary of each packet
    if packet.haslayer(IP):
        print("Processing Packet...")
        source_ip = packet[IP].src
        destination_ip = packet[IP].dst
        protocol = "TCP" if packet.haslayer(TCP) else "UDP" if packet.haslayer(UDP) else "Other"
        packet_size = len(packet)
        port = packet[TCP].sport if packet.haslayer(TCP) else packet[UDP].sport if packet.haslayer(UDP) else None
        source_mac = packet[Ether].src if packet.haslayer(Ether) else None
        destination_mac = packet[Ether].dst if packet.haslayer(Ether) else None

        # Basic classification
        traffic_type = "Normal"
        if protocol == "UDP" and port == 53:
            traffic_type = "Suspicious (DNS)"
        elif protocol not in ["TCP", "UDP"]:
            traffic_type = "Threat"

        print(f"Inserting: {source_ip} -> {destination_ip}, {protocol}, Port: {port}, Size: {packet_size}, Type: {traffic_type}")

        insert_packet(source_ip, destination_ip, source_mac, destination_mac, protocol, port, packet_size, traffic_type)
        print("✅ Packet inserted successfully!")

# Route to render frontend
@app.route('/')
def index():
    packets = fetch_all_packets()
    insights = fetch_all_insights()
    return render_template('index.html', packets=packets, insights=insights)



# API to fetch **all** insights
@app.route('/insights', methods=['GET'])
def get_insights():
    return jsonify(fetch_all_insights())


# API to fetch **all** packets
@app.route('/packets', methods=['GET'])
def get_packets():
    return jsonify(fetch_all_packets())


# Start packet sniffing
def start_sniffing():
    sniff(prn=process_packet, store=True)


# Run Flask App & Threads
if __name__ == "__main__":
    print("🚀 Starting Flask App with Real-Time Packet Sniffer and Traffic Analyzer...")

    # Start packet sniffing in a separate thread
    sniff_thread = threading.Thread(target=start_sniffing, daemon=True)
    sniff_thread.start()

    # Start traffic analysis in a separate thread
    analysis_thread = threading.Thread(target=analyze_traffic, daemon=True)
    analysis_thread.start()

    # Run Flask app with WebSockets
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
