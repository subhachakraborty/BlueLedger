mod routes;

use routes::handlers::*;
use actix_web::{get, post, web, App, HttpResponse, HttpServer, Responder};


pub async fn run() -> std::io::Result<()> {
    HttpServer::new(|| {
        App::new()
            .service(hello)
    })
    .bind(("127.0.0.1", 8000))?
        .run()
        .await
}
