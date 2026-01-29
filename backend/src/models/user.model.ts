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

export const User = model<IUser>("User", UserSchema);
