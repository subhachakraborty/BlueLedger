use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    pub username: String,
    pub exp: u64,
    pub iat: u64,
}
