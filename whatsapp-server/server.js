const express = require("express")
const cors = require("cors")
const { Client } = require("whatsapp-web.js")
const qrcode = require("qrcode")

const app = express()
app.use(cors())

let qrCodeData = null

const client = new Client()

client.on("qr", async (qr) => {
    qrCodeData = await qrcode.toDataURL(qr)
    console.log("QR generated")
})

client.on("ready", () => {
    console.log("WhatsApp client is ready and connected.");
})

client.on("authenticated", () => {
    console.log("WhatsApp authenticated successfully.");
})

client.on("disconnected", (reason) => {
    console.log("WhatsApp client disconnected. Reason:", reason);
})

client.initialize()

app.get("/sessions/qr", (req, res) => {
    if (qrCodeData) {
        res.json({ qr: qrCodeData })
    } else {
        res.json({ message: "QR Code not ready yet. Please try again." })
    }
})

app.post("/sessions/qr", (req, res) => {
    if (qrCodeData) {
        res.json({ qr: qrCodeData })
    } else {
        res.json({ message: "QR not ready yet" })
    }
})

app.listen(3100, () => {
    console.log("WhatsApp server running on port 3100")
})

app.get("/sessions/status",(req,res)=>{

if(client.info){

res.json({status:"connected"})

}else{

res.json({status:"disconnected"})

}

})


app.post("/sessions/reconnect",(req,res)=>{

client.initialize()

res.json({status:"reconnecting"})

})

// Update the /qr-page route to include auto-refresh functionality
app.get("/qr-page", (req, res) => {
    res.send(`
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Scan QR Code</title>
            <script>
                async function fetchQRCode() {
                    try {
                        const response = await fetch('/sessions/qr');
                        const data = await response.json();
                        if (data.qr) {
                            document.getElementById('qrCode').src = data.qr;
                        } else {
                            document.getElementById('qrMessage').innerText = data.message;
                        }
                    } catch (error) {
                        console.error('Error fetching QR code:', error);
                    }
                }

                setInterval(fetchQRCode, 5000); // Refresh every 5 seconds
                window.onload = fetchQRCode;
            </script>
        </head>
        <body>
            <h1>Scan QR Code</h1>
            <p id="qrMessage">Fetching QR Code...</p>
            <img id="qrCode" alt="WhatsApp QR Code" />
        </body>
        </html>
    `);
});