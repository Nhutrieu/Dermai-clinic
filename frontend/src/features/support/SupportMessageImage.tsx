import { useEffect, useState } from "react";
import { requestBlob } from "../../core/api";
import type { SupportMessage } from "../../core/types";

export default function SupportMessageImage({ message, token }: { message: SupportMessage; token: string }) {
  const [source, setSource] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl = "";
    setFailed(false);
    requestBlob(`/appointments/support/${message.id}/attachment`, token)
      .then(blob => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSource(objectUrl);
      })
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [message.id, token]);

  if (failed) return <small className="support-image-error">Không thể xem ảnh hoặc bạn không còn quyền truy cập.</small>;
  if (!source) return <span className="support-image-loading">Đang tải ảnh…</span>;
  return <img className="support-message-image" src={source} alt={message.attachmentOriginalName || "Ảnh do người dùng gửi"} />;
}