import { useEffect, useState } from "react";
import AppointmentList, { type AppointmentRefundPayment } from "../../components/PatientAppointmentList";
import { ApiError, request } from "../../core/api";
import { formatVnd } from "../../core/currency";
import type { Appointment, Patient } from "../../core/types";

export default function PatientAppointmentHistory({
    token, patient, appointments, changed, openBooking,
}: {
    token: string;
    patient: Patient;
    appointments: Appointment[];
    changed: (appointments: Appointment[]) => void;
    openBooking: () => void;
}) {
    const [refundPayments, setRefundPayments] = useState<Record<string, AppointmentRefundPayment>>({});
    const [feedback, setFeedback] = useState("");

    useEffect(() => {
        const cancelled = appointments.filter(item => item.status === "CANCELLED");
        if (!cancelled.length) { setRefundPayments({}); return; }
        let active = true;
        Promise.all(cancelled.map(async item => {
            try {
                const payment = await request<AppointmentRefundPayment>("/payments/booking/" + item.id, token);
                return [item.id, payment] as const;
            } catch (error) {
                if (error instanceof ApiError && error.status === 404) return [item.id, null] as const;
                throw error;
            }
        })).then(entries => {
            if (!active) return;
            setRefundPayments(Object.fromEntries(entries.filter((entry): entry is readonly [string, AppointmentRefundPayment] => entry[1] !== null)));
        }).catch(() => { if (active) setRefundPayments({}); });
        return () => { active = false; };
    }, [appointments, token]);

    async function requestDepositRefund(id: string) {
        const payment = await request<AppointmentRefundPayment>("/payments/booking/" + id + "/refunds/request", token, {
            method: "POST",
            body: JSON.stringify({ reason: "Bệnh nhân yêu cầu hoàn tiền cọc sau khi hủy lịch" }),
        });
        setRefundPayments(current => ({ ...current, [id]: payment }));
        setFeedback(`Đã gửi yêu cầu hoàn ${formatVnd(payment.refundAmount ?? payment.amount)} đến lễ tân theo chính sách phòng khám.`);
    }

    async function cancel(id: string, cancelReason: string) {
        const paid = ["PENDING_CONFIRMATION", "CONFIRMED"].includes(appointments.find(item => item.id === id)?.status || "");
        await request("/appointments/" + id + "/cancel", token, {
            method: "POST", body: JSON.stringify({ reason: cancelReason }),
        });
        changed(await request<Appointment[]>("/appointments/mine", token));
        setFeedback(paid
            ? "Đã hủy lịch. Bạn có thể xem lịch vừa hủy trong tab Lịch sử đặt lịch và bấm Yêu cầu hoàn tiền cọc nếu muốn hoàn cọc."
            : "Đã hủy lịch và trả lại khung giờ. Lịch vừa hủy đã chuyển sang tab Lịch sử đặt lịch. Không phát sinh hoàn tiền vì lịch chưa thanh toán cọc.");
    }

    async function hide(id: string) {
        await request("/appointments/" + id + "/hide", token, { method: "PATCH" });
        changed(await request<Appointment[]>("/appointments/mine", token));
    }

    return <div className="patient-booking">
        {feedback && <div className="booking-feedback booking-feedback-success" role="status" aria-live="polite">{feedback}</div>}
        <AppointmentList
            grouped
            token={token}
            appointments={appointments}
            cancel={cancel}
            refundPayments={refundPayments}
            requestRefund={requestDepositRefund}
            hide={hide}
            patientName={patient.fullName}
            onBookNew={openBooking}
        />
    </div>;
}
