use actix_web::{get, post, web, HttpResponse, Responder, Result};
use serde_json::json;
use crate::models::geojson::*;

#[get("/")]
pub async fn hello() -> impl Responder {
    HttpResponse::Ok().body("Hello world")
}

#[post("/geojson")]
pub async fn geo(geojson: web::Json<PolygonGeoJson>) -> impl Responder {
    let geojson = geojson.into_inner();
    HttpResponse::Ok().json(json!({
        "Name": geojson.name,
        "Geometry": geojson.geometry,
    }))
}
