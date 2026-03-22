use serde::{Serialize, Deserialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    pub email: String,
    pub password: String,
    pub exp: u64,
}
