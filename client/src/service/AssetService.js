import api from "../http";


export default class AssetService {
    static async initUpload(data) {
        return api.post("/assets/uploads/init", data);
    }

    static async finalizeUpload(assetId) {
        return api.post(`/assets/uploads/${assetId}/finalize`);
    }

    static async uploadFile(uploadUrl, file, headers = {}) {
        return fetch(uploadUrl, {
            method: "PUT",
            headers,
            body: file,
        });
    }
}
