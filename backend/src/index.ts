import express from "express";
import { Schema, model, connect } from 'mongoose';
import { User } from "./db";
import dotenv from 'dotenv'
dotenv.config({ path: './.env' })

const app = express();
const PORT = 8000;
let DB_URL: string | undefined = process.env.DATABASE_URL;

// -- Middleware --
app.use(express.json())

if (DB_URL == undefined) {
    DB_URL = "http://localhost:27017/testDB";
}

async function connectDB(conn_string: string) {
    // 3. Connect to MongoDB
    await connect(conn_string)
}

// try {
//     connectDB(DB_URL);
//     console.log("Database connection is successful")
// } catch(err) {
//     console.log(err)
// }

// app.get("/", (req, res) => {
//     res.json({
//         "message": "Testing"
//     });
// });

app.post("/test", (req, res) => {
    const username = req.body.username;
    const password = req.body.password;
    const data = {
        username,
        password
    }
    console.log(data)
});

app.listen(PORT, () => {
    console.log(`Server is listening on http://localhost:${PORT}`);
})
