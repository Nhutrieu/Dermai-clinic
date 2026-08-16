import { useEffect, useState } from "react";
import { request } from "../../core/api";
import type { ClinicReview } from "../../core/types";

type ReviewListProps = {
    reviews: ClinicReview[];
    error?: string;
    onModerate: (reviewId: string, status: "APPROVED" | "HIDDEN") => Promise<void>;
};

export function AdminClinicReviewList({ reviews, error, onModerate }: ReviewListProps) {
    return <section className="panel admin-reviews">
        <h2>Duyệt đánh giá phòng khám</h2>
        {error && <p role="alert">{error}</p>}
        {!error && reviews.length === 0 && <p>Không có đánh giá đang chờ duyệt.</p>}
        {reviews.map(review => <article key={review.id}>
            <div>
                {/* React text nodes escape stored names/comments before they reach the DOM. */}
                <b>{review.rating}/5 sao · {review.displayName}</b>
                <p>{review.comment}</p>
            </div>
            <button type="button" onClick={() => void onModerate(review.id, "APPROVED")}>Duyệt</button>
            <button type="button" onClick={() => void onModerate(review.id, "HIDDEN")}>Ẩn</button>
        </article>)}
    </section>;
}

export default function AdminClinicReviews({ token }: { token: string }) {
    const [reviews, setReviews] = useState<ClinicReview[]>([]);
    const [error, setError] = useState("");

    async function load() {
        try {
            const items = await request<ClinicReview[]>("/appointments/reviews", token);
            setReviews(items.filter(item => item.status === "PENDING"));
            setError("");
        } catch (cause) {
            setError((cause as Error).message);
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

    return <AdminClinicReviewList reviews={reviews} error={error} onModerate={moderate} />;
}
