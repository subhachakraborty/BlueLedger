// import https from "node:https";

import { XMLParser } from "fast-xml-parser";
import { PutObjectCommand, S3Client } from "@aws-sdk/client-s3";
import { fromIni } from "@aws-sdk/credential-providers";
import { HttpRequest } from "@smithy/protocol-http";
import {
    getSignedUrl,
    S3RequestPresigner,
} from "@aws-sdk/s3-request-presigner";
import { parseUrl } from "@smithy/url-parser";
import { formatUrl } from "@aws-sdk/util-format-url";
import { Hash } from "@smithy/hash-node";

const createPresignedUrlWithoutClient = async ({ region, bucket, key }) => {
    const url = parseUrl(`https://${bucket}.s3.${region}.amazonaws.com/${key}`);
        const presigner = new S3RequestPresigner({
        credentials: fromIni(),
        region,
        sha256: Hash.bind(null, "sha256"),
    });

    const signedUrlObject = await presigner.presign(
        new HttpRequest({ ...url, method: "PUT" }),
    );
    return formatUrl(signedUrlObject);
};

const createPresignedUrlWithClient = ({ region, bucket, key }) => {
    const client = new S3Client({ region });
    const command = new PutObjectCommand({ Bucket: bucket, Key: key });
    return getSignedUrl(client, command, { expiresIn: 3600 });
};

/**
 * Make a PUT request to the provided URL.
 *
 * @param {string} url
 * @param {string} data
 */
const put = (url, data) => {
    return new Promise((resolve, reject) => {
        const req = https.request(
            url,
            { method: "PUT", headers: { "Content-Length": new Blob([data]).size } },
            (res) => {
                let responseBody = "";
                res.on("data", (chunk) => {
                    responseBody += chunk;
                });
                res.on("end", () => {
                    const parser = new XMLParser();
                    if (res.statusCode >= 200 && res.statusCode <= 299) {
                        resolve(parser.parse(responseBody, true));
                    } else {
                        reject(parser.parse(responseBody, true));
                    }
                });
            },
        );
        req.on("error", (err) => {
            reject(err);
        });
        req.write(data);
        req.end();
    });
};

/**
 * Create two presigned urls for uploading an object to an S3 bucket.
 * The first presigned URL is created with credentials from the shared INI file
 * in the current environment. The second presigned URL is created using an
 * existing S3Client instance that has already been provided with credentials.
 * @param {{ bucketName: string, key: string, region: string }}
 */
export const main = async ({ bucketName, key, region }) => {
    try {
        const noClientUrl = await createPresignedUrlWithoutClient({
            bucket: bucketName,
            key,
            region,
        });

        const clientUrl = await createPresignedUrlWithClient({
            bucket: bucketName,
            region,
            key,
        });

        // After you get the presigned URL, you can provide your own file
        // data. Refer to put() above.
        console.log("Calling PUT using presigned URL without client");
        await put(noClientUrl, "Hello World");

        console.log("Calling PUT using presigned URL with client");
        await put(clientUrl, "Hello World");

        console.log("\nDone. Check your S3 console.");
    } catch (caught) {
        if (caught instanceof Error && caught.name === "CredentialsProviderError") {
            console.error(
                `There was an error getting your credentials. Are your local credentials configured?\n${caught.name}: ${caught.message}`,
            );
        } else {
            throw caught;
        }
    }
};


