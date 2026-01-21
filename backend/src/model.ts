import { Schema, model, connect, Types } from 'mongoose';

export interface IUser {
    username: string;
    email: string;
    password: string;
    // role: "admin" | "user";
    _id?: Types.ObjectId;
    createdAt?: Date;
    updatedAt?: Date;
}

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

const UserSchema = new Schema<IUser>({
    username: {
        type: String,
        required: true,
        trim: true,
        minlength: 3,
    },
    email: {
        type: String,
        required: true,
        unique: true,
        lowercase: true,
        trim: true,
        // add regex for basic validation
        // match: [regexp, "Enter valid email address"]
    },
    password: {
        type: String,
        required: true,
        minlength: 6
    },
    // role: {
    //     type: String,
    //     enum: ["user", "admin"],
    //     default: "user"
    // }
});

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
    user: {
        type: Schema.Types.ObjectId,
        ref: "User",
        required: true,
        index: true,
    }
});

const User = model<IUser>("User", UserSchema);
const Post = model<IPost>("Post", PostSchema);

export { User, Post };
