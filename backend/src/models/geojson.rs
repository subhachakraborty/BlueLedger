use serde::{Deserialize, Serialize};

// Example data
// {
//   "name": "Delivery Zone A",
//   "geometry": {
//     "type": "Polygon",
//     "coordinates": [
//       [
//         [81.15, 19.48],
//         [81.15, 19.45],
//         [81.20, 19.45],
//         [81.20, 19.48],
//         [81.15, 19.48]
//       ]
//     ]
//   }
// }

type Point = Vec<f64>;
type Coordinates = Vec<Vec<Point>>;

#[derive(Debug, Serialize, Deserialize)]
pub struct Geometry {
    #[serde(rename = "type")]
    pub polygon_type: String,
    pub coordinates: Coordinates,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PolygonGeoJson {
    pub name: String,
    pub geometry: Geometry,
}
