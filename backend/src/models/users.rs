use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct SignupUser {
    pub firstname: String,
    pub lastname: String,
    pub username: String,
    pub password: String,
}

#[derive(Debug, Deserialize)]
pub struct LoginUser {
    pub username: String,
    pub password: String,
}
