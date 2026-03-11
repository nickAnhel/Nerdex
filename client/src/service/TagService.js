import api from "../http";


export default class TagService {
    static async getSuggestions(query, limit = 10) {
        return api.get("/tags/suggestions", {
            params: {
                query,
                limit,
            },
        });
    }
}
