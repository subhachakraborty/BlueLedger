import { Schema, model, connect, Types } from 'mongoose';

export interface IPost {
    title: string;
    description: string;

    // S3 Data
    imageKey: string;
    originalName: string;
    mimetype: string;
    size: number;

    // user reference
    user: Types.ObjectId; // Id for the user document

    // System Time
    createdAt?: Date;
    updatedAt?: Date;
}
const PostSchema = new Schema<IPost>({
    title: {
        type: String,
        required: true,
    },
    description: {
        type: String,
        required: true,
    },
    imageKey: {
        type: String,
        required: true,
    },
    originalName: {
        type: String,
        required: true,
    },
    mimetype: {
        type: String,
        required: true,
    },

    // Link to the user collection
    // Add on feature while authentication
    user: {
        type: Schema.Types.ObjectId,
        ref: "User",
        required: true,
        index: true,
    }
});

export const Post = model<IPost>("Post", PostSchema);

