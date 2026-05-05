import api from "../http";


export default class VideoService {
    static async createVideo(data) {
        return api.post("/videos", data);
    }

    static async getVideos(params) {
        return api.get("/videos/list", { params });
    }

    static async getVideo(videoId) {
        return api.get(`/videos/${videoId}`);
    }

    static async getVideoEditor(videoId) {
        return api.get(`/videos/${videoId}/editor`);
    }

    static async updateVideo(videoId, data) {
        return api.put(`/videos/${videoId}`, data);
    }

    static async deleteVideo(videoId) {
        return api.delete(`/videos/${videoId}`);
    }

    static async likeVideo(videoId) {
        return api.post(`/videos/${videoId}/like`);
    }

    static async unlikeVideo(videoId) {
        return api.delete(`/videos/${videoId}/like`);
    }

    static async dislikeVideo(videoId) {
        return api.post(`/videos/${videoId}/dislike`);
    }

    static async undislikeVideo(videoId) {
        return api.delete(`/videos/${videoId}/dislike`);
    }
}
