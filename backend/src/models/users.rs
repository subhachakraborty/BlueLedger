use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct SignupUser {
    pub firstname: String,
    pub lastname: String,
    pub email: String,
    pub password: String,
}

#[derive(Debug, Deserialize)]
pub struct LoginUser {
    pub email: String,
    pub password: String,
}
