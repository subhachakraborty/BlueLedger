import express from "express";
import { Schema, model, connect } from 'mongoose';
import dotenv from 'dotenv'
import * as Minio from 'minio'
import { User } from "./db";
import multer from "multer";
import path from "path";
import { fileURLToPath } from "url";

const upload = multer({ dest: 'uploads/' })
// const __filename = fileURLToPath(import.meta.url);
// const dirname = path.dirname(__filename);

// const filePath = "../uploads/"
// const filename = path.basename(filePath)

dotenv.config({ path: './.env' })

// Console: https://play.min.io:9443/
const minioClient = new Minio.Client({
    endPoint: 'play.min.io',
    port: 9000,
    useSSL: true,
    accessKey: 'Q3AM3UQ867SPQQA43P2F',
    secretKey: 'zuf+tfteSlswRu7BJ86wekitnifILbZam1KYY3TG',
})

// set up multer storage
const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        cb(null, '/uploads')
    },
    filename: function (req, file, cb) {
        cb(null, Date.now() + '-' + file.originalname);
    }
});

const app = express();
const PORT = 8000;
let DB_URL: string | undefined = process.env.DATABASE_URL;

// -- Middleware --
app.use(express.json())

if (DB_URL == undefined) {
    DB_URL = "mongodb://localhost:27017/testDB";
}

async function connectDB(conn_string: string) {
    // 3. Connect to MongoDB
    await connect(conn_string)
}

try {
    connectDB(DB_URL);
    console.log("Database connection is successful")
} catch(err) {
    console.log(err)
}

// app.get("/", (req, res) => {
//     res.json({
//         "message": "Testing"
//     });
// });

app.post("/test", async (req, res) => {
    const username = req.body.username;
    const password = req.body.password;

    const user = new User({
        username,
        password
    });
    try {
        const response = await user.save();
        res.json({
            "message": "Saved successful",
            "id": response._id,
        })
    } catch(err) {
        console.log("Submission did not happen");
    }
});

app.get("/", (req, res) => {
    res.send(`
             <h1>File Upload Demo</h1>
             <form action="/upload/images" method="post" enctype="multipart/form-data">
             <input type="file" name="uploadedFile" />
             <button type="submit">Upload</button>
             </form>
             `);
});

const bucket = "blue-ledger-objects";

app.post("/upload/images", upload.single('uploadedFile'), async (req, res) => {
    console.log(req.file); // Contains file info
    if (req.file != undefined) {
        // finename
        const sourceFileName = req.file.originalname;
        // file path
        const sourceFilePath = req.file.path;
        const exists = await minioClient.bucketExists(bucket)
        if (exists) {
            console.log("Bucket " + bucket + " exists");
        } else {
            await minioClient.makeBucket(bucket, "us-east-1");
            console.log("Bucket " + bucket + " created in us-east-1.");
        }

        let metaData = {
            "Content-Type": "image/jpg"
        }
        await minioClient.fPutObject(bucket, req.file.originalname, sourceFilePath, metaData)
        console.log("File " + sourceFilePath + " upload as object " + req.file.originalname + " in bucket " + bucket);
        res.send(`File uploaded successfully: ${req.file.originalname}`);
    }
    else {
        res.send("Error while uploading images")
    }
});

app.listen(PORT, () => {
    console.log(`Server is listening on http://localhost:${PORT}`);
})
