document.addEventListener("DOMContentLoaded", function () {
    const socket = io();

    function addPacket(packet) {
        const packetList = document.getElementById("packet-list");
        const div = document.createElement("div");
        div.className = "packet";
        div.innerHTML = `<strong>${packet.source_ip} ➝ ${packet.destination_ip}</strong> 
                         [${packet.protocol}] Port: ${packet.port} 
                         <span style="color: ${packet.traffic_type === 'Threat' ? 'red' : packet.traffic_type.includes('Suspicious') ? 'orange' : 'green'}">
                         (${packet.traffic_type})</span>`;
        packetList.prepend(div);
    }

    function addInsight(insight) {
        const insightList = document.getElementById("insight-list");
        const div = document.createElement("div");
        div.className = "insight";
        div.innerHTML = `<strong>${insight.insight}</strong><br>
                         <em>${insight.recommendation}</em>`;
        insightList.prepend(div);
    }

    // Fetch initial data from API
    fetch("/packets")
        .then(response => response.json())
        .then(data => {
            data.forEach(addPacket);
        });

    fetch("/insights")
        .then(response => response.json())
        .then(data => {
            data.forEach(addInsight);
        });

    // Real-time updates using WebSockets
    socket.on("update_packets", function (packets) {
        document.getElementById("packet-list").innerHTML = "";
        packets.forEach(addPacket);
    });

    socket.on("update_insights", function (insights) {
        document.getElementById("insight-list").innerHTML = "";
        insights.forEach(addInsight);
    });
});
