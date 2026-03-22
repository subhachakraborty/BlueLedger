mod routes;
mod models;
mod state;
mod config;
mod middleware;

use actix_web::{web, App, HttpServer};
use routes::handlers::*;
use dotenvy::dotenv;
use sqlx::{Pool, Postgres};
use sqlx::postgres::PgPoolOptions;
use crate::state::state::AppState;
use crate::config::Config;
use crate::middleware::auth::*;

pub async fn run() -> std::io::Result<()> {

    // Must run before any encode/decode. Also avoids ambiguity if crate features unify badly.
    rustls::crypto::aws_lc_rs::default_provider()
        .install_default()
        .expect("Can't set crypto provider");

    env_logger::init_from_env(env_logger::Env::default().default_filter_or("debug"));
    dotenv().ok();

    // load the config via envs
    let config: Config = envy::from_env().unwrap();

    let pool: Pool<Postgres> = match PgPoolOptions::new()
        .max_connections(3)
        .connect(&config.database_url.clone())
        .await
        {
            Ok(pool) => {
                println!("Database connection is successful");
                pool
            }
            Err(err) => {
                println!("Failed to connect to the database {:?}", err);
                std::process::exit(1);
            }
        };

    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(AppState {
                db: pool.clone(),
                config: config.clone(),
            }))
            .service(hello)
            .service(signup)
            .service(login)
            .service(
                web::scope("")
                .wrap(JwtMiddleware::new(config.secret_key.clone()))
                .service(geo)
            )
    })
    .bind(("0.0.0.0", 9000))?
        .workers(3)
        .run()
        .await
}
