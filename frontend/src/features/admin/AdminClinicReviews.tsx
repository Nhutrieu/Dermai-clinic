import { useEffect, useState } from "react";
import { Check, EyeOff, MessageSquareCheck, Star } from "lucide-react";
import { request } from "../../core/api";
import type { ClinicReview } from "../../core/types";
import { EmptyState, ErrorState, StateSkeleton } from "../../components/Ui";

type ReviewListProps = {
    reviews: ClinicReview[];
    error?: string;
    loading?: boolean;
    onRetry?: () => void;
    onModerate: (reviewId: string, status: "APPROVED" | "HIDDEN") => Promise<void>;
};

export function AdminClinicReviewList({ reviews, error, loading = false, onRetry, onModerate }: ReviewListProps) {
    return <section className="panel admin-reviews">
        <header className="admin-reviews-heading"><div><h2>Duyệt đánh giá phòng khám</h2><p>Kiểm tra nội dung trước khi đánh giá xuất hiện trên trang chủ.</p></div><span>{reviews.length} chờ duyệt</span></header>
        {loading && <StateSkeleton rows={2} label="Đang tải đánh giá phòng khám" />}
        {!loading && error && <ErrorState compact title="Không thể tải đánh giá" description={error} retry={onRetry} />}
        {!loading && !error && reviews.length === 0 && <EmptyState compact icon={MessageSquareCheck} title="Không có đánh giá đang chờ duyệt" description="Đánh giá mới từ bệnh nhân đã hoàn tất lượt khám sẽ xuất hiện tại đây." />}
        {!loading && reviews.map(review => <article className="admin-review-card" key={review.id}>
            <div className="admin-review-avatar" aria-hidden="true">{review.displayName.trim().charAt(0).toUpperCase()}</div>
            <div className="admin-review-content">
                {/* React text nodes escape stored names/comments before they reach the DOM. */}
                <div className="admin-review-meta">
                    <b>{review.displayName}</b>
                    <span><Star size={14} fill="currentColor" /> {review.rating}/5</span>
                </div>
                <p>{review.comment || "Người dùng không để lại nội dung đánh giá."}</p>
            </div>
            <div className="admin-review-actions">
                <button className="admin-review-approve" type="button" onClick={() => void onModerate(review.id, "APPROVED")}><Check size={17} /> Duyệt</button>
                <button className="admin-review-hide" type="button" onClick={() => void onModerate(review.id, "HIDDEN")}><EyeOff size={17} /> Ẩn</button>
            </div>
        </article>)}
    </section>;
}

export default function AdminClinicReviews({ token }: { token: string }) {
    const [reviews, setReviews] = useState<ClinicReview[]>([]);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(true);

    async function load() {
        setLoading(true);
        try {
            const items = await request<ClinicReview[]>("/appointments/reviews", token);
            setReviews(items.filter(item => item.status === "PENDING"));
            setError("");
        } catch (cause) {
            setError((cause as Error).message);
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        void load();
    }, [token]);

    async function moderate(reviewId: string, status: "APPROVED" | "HIDDEN") {
        try {
            await request(`/appointments/reviews/${reviewId}`, token, {
                method: "PATCH",
                body: JSON.stringify({ status }),
            });
            await load();
        } catch (cause) {
            setError((cause as Error).message);
        }
    }

    return <AdminClinicReviewList reviews={reviews} error={error} loading={loading} onRetry={() => void load()} onModerate={moderate} />;
}
