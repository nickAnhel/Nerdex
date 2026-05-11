import api from "../http";


export default class MomentService {
    static async createMoment(data) {
        return api.post("/moments", data);
    }

    static async getFeed(params) {
        return api.get("/moments/feed", { params });
    }

    static async getMoments(params) {
        return api.get("/moments/list", { params });
    }

    static async getMoment(momentId) {
        return api.get(`/moments/${momentId}`);
    }

    static async getMomentEditor(momentId) {
        return api.get(`/moments/${momentId}/editor`);
    }

    static async updateMoment(momentId, data) {
        return api.put(`/moments/${momentId}`, data);
    }

    static async deleteMoment(momentId) {
        return api.delete(`/moments/${momentId}`);
    }
}
