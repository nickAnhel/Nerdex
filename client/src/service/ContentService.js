import api from "../http";


export default class ContentService {
    static async getFeed(params) {
        return api.get("/contents/list", { params });
    }

    static async getSubscriptionsFeed(params) {
        return api.get("/contents/subscriptions", { params });
    }
}
