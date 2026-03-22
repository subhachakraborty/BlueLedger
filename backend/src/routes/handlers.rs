use crate::models::jwt::Claims;
use crate::models::{geojson::*, users::*};
use crate::state::state::AppState;
use actix_web::{
    HttpResponse, Responder, get, post,
    web::{Data, Json},
};
use bcrypt::{DEFAULT_COST, hash, verify};
use chrono::{Duration, Utc};
use jsonwebtoken::{EncodingKey, Header, encode};
use serde_json::json;
use sqlx::Row;
use uuid::Uuid;

#[get("/")]
pub async fn hello() -> impl Responder {
    HttpResponse::Ok().body("Hello world")
}

#[post("/signup")]
pub async fn signup(state: Data<AppState>, payload: Json<SignupUser>) -> impl Responder {
    let user = payload.into_inner();
    // hash the password
    let id = Uuid::new_v4();
    let hashed_password = match hash(user.password, DEFAULT_COST) {
        Ok(value) => value,
        Err(_) => {
            return HttpResponse::InternalServerError().json(json!({
                "message": "Password hashing failed"
            }));
        }
    };

    let inserted_row = sqlx::query(
        r#"
        INSERT INTO users (id, firstname, lastname, email, password)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        "#,
    )
    .bind(id)
    .bind(user.firstname)
    .bind(user.lastname)
    .bind(user.email)
    .bind(hashed_password)
    .fetch_one(&state.db)
    .await;

    match inserted_row {
        Ok(_) => HttpResponse::Ok().json(json!({
        "message": "Successfully created user",
        "id": id,
        })),
        Err(_) => HttpResponse::InternalServerError().json(json!({
            "message": "User creation failed",
        })),
    }
}

#[post("/login")]
pub async fn login(state: Data<AppState>, payload: Json<LoginUser>) -> impl Responder {
    let user = payload.into_inner();

    // check if the user exists
    let result = sqlx::query(
        r#"
        SELECT email, password from users
        WHERE email=$1
        "#,
    )
    .bind(&user.email)
    .fetch_one(&state.db)
    .await;
    match result {
        Ok(row) => {
            // verify the user with password
            let hashed_password = row.get("password");
            let is_valid: bool = verify(&user.password, hashed_password).unwrap_or(false);
            if is_valid {
                let secret = state.config.secret_key.clone();
                let claims = Claims {
                    email: user.email,
                    password: user.password,
                    exp: (Utc::now() + Duration::hours(24)).timestamp() as u64,
                };

                // This will create a JWT using HS256 as algorithm
                let token = encode(
                    &Header::default(),
                    &claims,
                    &EncodingKey::from_secret(secret.as_ref()),
                )
                .unwrap();

                HttpResponse::Ok().json(json!({
                    "message": "Login Successful",
                    "token": token,
                }))
            } else {
                HttpResponse::Unauthorized().json(json!({
                    "message": "Invalid email or password"
                }))
            }
        }

        Err(_) => HttpResponse::NotFound().json(json!({
            "message": "User not found"
        })),
    }
}

#[post("/geojson")]
pub async fn geo(geojson: Json<PolygonGeoJson>) -> impl Responder {
    let geojson = geojson.into_inner();
    HttpResponse::Ok().json(json!({
        "Name": geojson.name,
        "Geometry": geojson.geometry,
    }))
}
