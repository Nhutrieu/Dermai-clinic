import { useEffect, useState } from "react";
import { requestBlob } from "../core/api";

type Props = {
  token: string;
  identityId: string;
  fallback: string;
  className: string;
  hasAvatar?: boolean;
};

export default function AuthenticatedAvatar({ token, identityId, fallback, className, hasAvatar }: Props) {
  const [source, setSource] = useState("");

  useEffect(() => {
    if (!identityId || hasAvatar === false) {
      setSource("");
      return;
    }

    let active = true;
    let objectUrl = "";
    requestBlob(`/auth/accounts/${identityId}/avatar`, token)
      .then(blob => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSource(objectUrl);
      })
      .catch(() => {
        // Missing avatars intentionally fall back to initials without surfacing an error.
        if (active) setSource("");
      });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [hasAvatar, identityId, token]);

  return <span className={className} aria-hidden="true">
    {source ? <img src={source} alt="" /> : fallback}
  </span>;
}
