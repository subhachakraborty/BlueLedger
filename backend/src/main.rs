use server::run;

// Entrypoint -> main function
#[actix_web::main]
async fn main() -> std::io::Result<()> {
    run().await
}
