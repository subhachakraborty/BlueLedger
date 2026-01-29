export function jsonParsing(geojson: any): any {
    if (typeof geojson == "string") {
        return JSON.parse(geojson)
    }

    return geojson;
}

export function assertNumericCoordinates(value: any) {
    if (Array.isArray(value)) {
        value.forEach(assertNumericCoordinates);
        return;
    }

    if (typeof value !== "number" || !Number.isFinite(value)) {
        throw new Error(
            `Invalid coordinate value: ${JSON.stringify(value)}`
        );
    }
}

export function featureExtraction(features: any[]) {
    if(!Array.isArray(features)) {
        throw new Error("GeoJson features must be an array");
    }
    return features.map((feature: any) => {
        if(!feature.geometry) {
            throw new Error("feature is missing geometry");
        }

        const {type, coordinates} = feature.geometry;
        assertNumericCoordinates(coordinates);

        if(type == "Point") {

            if (!Array.isArray(coordinates) || coordinates.length !== 2) {
                throw new Error("Invalid Point coordinates format");
            }

            const lng = Number(coordinates[0]);
            const lat = Number(coordinates[1]);

            if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
                throw new Error("Invalid Point coordinates");
            }

            if(Number.isNaN(lng) || Number.isNaN(lat)) {
                throw new Error("Invalid Point coordinates");
            }

            return {
                type: "Point",
                coordinates: [lng, lat],
            };
        }

        if (!Array.isArray(coordinates)) {
            throw new Error(`Invalid coordinates for ${type}`);
        }

        return {
            type,
            coordinates,
        };
    });
}
