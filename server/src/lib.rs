mod routes;
mod models;

use actix_web::{get, post, web, App, HttpResponse, HttpServer, Responder};
use routes::handlers::*;
use models::geojson::*;

pub async fn run() -> std::io::Result<()> {
    HttpServer::new(|| {
        App::new()
            .service(hello)
            .service(geo)
    })
    // random ip binding with random port
    // need to use the TCPListener for random port each time server start
    // use hot realod
    .bind(("0.0.0.0", 8000))?
        .workers(2)
        .run()
        .await
}
