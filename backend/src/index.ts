import express from "express";
import { Schema, model, connect } from 'mongoose';
import dotenv from 'dotenv'
import multer from "multer";
import multerS3 from "multer-s3";
import { S3Client } from "@aws-sdk/client-s3";
import path from "path";
// import { fileURLToPath } from "url";
import * as config from "./config.json";
import { User, Post } from "./model";
import * from "./"
// -- Server Config
const app = express();
dotenv.config({ path: './.env', quiet: true })

// -- Middleware --
app.use(express.json())


// -- Multer Client with aws s3
// set up multer storage
const accessKeyId = process.env.ACCESS_KEY_ID;
const secretAccessKey = process.env.SECRET_ACCESS_KEY;
if (!accessKeyId || !secretAccessKey) {
    throw new Error("AWS Credentials missing. Please check your .env file.");
}


const s3Client = new S3Client({
    region: 'us-east-1',
    credentials: {
        accessKeyId,
        secretAccessKey,
    }
});


const upload = multer({
    storage: multerS3({
        s3: s3Client,
        bucket: "test-ledger-3030",
        // acl: 'public-read', // <- change this based on the access level
        contentType: multerS3.AUTO_CONTENT_TYPE,
        metadata: function (req, file, cb) {
            cb(null, {fieldName: file.fieldname});
        },
        key: function(req, file, cb) {
            cb(null, `${Date.now()}-${file.originalname}`) // <- key to store
        }
    })
});


//  -- Database Configuration
let DB_URL: string | undefined = process.env.DATABASE_URL;
// -- Override if there is no .env file | no url in .env
if (DB_URL == undefined || !DB_URL) {
    DB_URL = config.DB_URL;
}

async function connectDB(conn_string: string) {
    // 3. Connect to MongoDB
    try {
        await connect(conn_string)
        console.log("Database connection is successful")
    } catch(err) {
        console.error("Database connection issue: ", err);
    }
}

// -- Connect to the DB
connectDB(DB_URL);

app.get("/single-upload", (req, res) => {
    res.send(`
        <h1>File Upload Demo</h1>
        <form action="/upload/single/image" method="post" enctype="multipart/form-data">
            <input type="text" name="userId" placeholder='mock userId' />
            <input type="text" name="title" placeholder="title" />
            <input type="text" name="description" placeholder="description" />

            <textarea name="geojson" placeholder="paste geojson data" rows="10" cols='50'></textarea>
            <!-- upload multiple images -->
            <input type="file" name="uploadedFile" />
            <button type="submit">Upload</button>
        </form>
    `);
});

app.get("/multiple-upload", (req, res) => {
    res.send(`
        <h1>File Upload Demo</h1>
        <form action="/upload/multiple/image" method="post" enctype="multipart/form-data">
            <input type="text" name="userId" placeholder='mock userId' />
            <input type="text" name="title" placeholder="title" />
            <input type="text" name="description" placeholder="description" />

            <textarea name="geojson" placeholder="paste geojson data" rows="10" cols='50'></textarea>
            <!-- upload multiple images -->
            <input type="file" name="uploadedFile" multiple/>
            <button type="submit">Upload</button>
        </form>
    `);
});

app.post("/upload/multiple/image", upload.array('uploadedFile', 2), async (req, res) => {
    try {

        console.log(req.files, req.body);

        if(!req.files){
            return res.status(400).json({
                error: "No file uploaded",
            })
        }

        const post = new Post({
            title: req.body.title,
            description: req.body.description,
            images: (req.files as Express.Multer.File[]).map((file: any) => {
                return {
                    imageKey: file.key,
                    originalName: file.originalname,
                    mimetype: file.mimetype,
                    size: file.size,
                }
            }),

            // has to fix this Point should be numeric but got object error
            locations: (() => {
                let geojson = req.body.geojson;

                if (typeof geojson === "string") {
                    geojson = JSON.parse(geojson);
                }

                return geojson.features.map((feature: any) => {
                    const { type, coordinates } = feature.geometry;

                    if (type === "Point") {
                        const lng = Number(coordinates[0]);
                        const lat = Number(coordinates[1]);

                        if (Number.isNaN(lng) || Number.isNaN(lat)) {
                            throw new Error("Invalid Point coordinates");
                        }

                        return {
                            type,
                            coordinates: [lng, lat],
                        };
                    }

                    return {
                        type,
                        coordinates,
                    };
                });
            })(),
            user: req.body.userId,
        });

        await post.save();

        res.status(201).json({ 
            message: "Upload successful", 
            post: post
        });

    } catch(error) {
        console.error(error);
        res.status(500).json({
            error: "Serving error during upload",
        })
    }
});


app.listen(config.PORT, () => {
    console.log(`Server is listening on http://localhost:${config.PORT}`);
})
