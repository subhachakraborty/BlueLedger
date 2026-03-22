use serde::Deserialize;

#[derive(Deserialize, Debug, Clone)]
pub struct Config {
    // field names should match exactly like env vars
    pub database_url: String,
    pub secret_key: String,
}
