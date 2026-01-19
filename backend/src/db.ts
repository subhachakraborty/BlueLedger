import { Schema, model, connect } from 'mongoose';

// 1. Create a Schema corresponding to the document interface.
const userSchema = new Schema({
    name: { type: String, required: true },
    email: { type: String, required: true },
});

// 2. Create a Model.
export const User = model('User', userSchema);

