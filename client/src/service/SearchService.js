import api from "../http";


export default class SearchService {
    static async search(params) {
        return api.get("/search", { params });
    }

    static async popular(params) {
        return api.get("/search/popular", { params });
    }
}
