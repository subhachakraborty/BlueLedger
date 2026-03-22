use crate::models::jwt::Claims;
use actix_web::{
    Error, HttpMessage, HttpResponse,
    body::{BoxBody, EitherBody},
    dev::{Service, ServiceRequest, ServiceResponse, Transform, forward_ready},
};
use futures::future::{LocalBoxFuture, Ready, ok};
use jsonwebtoken::{Algorithm, DecodingKey, Validation, decode};
use serde_json::json;

pub struct JwtMiddleware {
    secret_key: String,
}

impl JwtMiddleware {
    pub fn new(secret_key: String) -> Self {
        Self { secret_key }
    }
}

impl<S, B> Transform<S, ServiceRequest> for JwtMiddleware
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = Error>,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<EitherBody<BoxBody, B>>;
    type Error = Error;
    type InitError = ();
    type Transform = JwtMiddlewareService<S>;
    type Future = Ready<Result<Self::Transform, Self::InitError>>;

    fn new_transform(&self, service: S) -> Self::Future {
        ok(JwtMiddlewareService {
            service,
            secret_key: self.secret_key.clone(),
        })
    }
}

pub struct JwtMiddlewareService<S> {
    service: S,
    secret_key: String,
}

impl<S, B> Service<ServiceRequest> for JwtMiddlewareService<S>
where
    S: Service<ServiceRequest, Response = ServiceResponse<B>, Error = Error>,
    S::Future: 'static,
    B: 'static,
{
    type Response = ServiceResponse<EitherBody<BoxBody, B>>;
    type Error = Error;
    type Future = LocalBoxFuture<'static, Result<Self::Response, Self::Error>>;

    forward_ready!(service);

    fn call(&self, req: ServiceRequest) -> Self::Future {
        let token = req
            .headers()
            .get("Authorization")
            .and_then(|v| v.to_str().ok())
            .and_then(|v| v.strip_prefix("Bearer "))
            .map(|v| v.to_owned());

        // secret is also clone before req is moved
        let secret = self.secret_key.clone();

        let token = match token {
            Some(t) => t,
            None => {
                let response = req.into_response(HttpResponse::Unauthorized().json(json!({
                        "error": "Missing token"
                })));

                return Box::pin(async move { Ok(response.map_into_left_body()) });
            }
        };

        let claims = match decode::<Claims>(
            &token,
            &DecodingKey::from_secret(secret.as_ref()),
            &Validation::new(Algorithm::HS256),
        ) {
            Ok(data) => data.claims,
            Err(_) => {
                let response = req.into_response(HttpResponse::Unauthorized().json(json!({
                        "error": "Invalid Token"
                })));

                return Box::pin(async move { Ok(response.map_into_left_body()) });
            }
        };
        // inject claims into request extensions
        req.extensions_mut().insert(claims);

        // token is valid, forward to handler
        let fut = self.service.call(req);

        Box::pin(async move {
            let res = fut.await?;

            Ok(res.map_into_right_body())
        })
    }
}
