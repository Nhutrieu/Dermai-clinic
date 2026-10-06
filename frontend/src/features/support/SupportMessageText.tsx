const URL_PATTERN = /(https?:\/\/[^\s]+)/g;

export default function SupportMessageText({ body }: { body: string }) {
  return <>
    {body.split(URL_PATTERN).map((part, index) => part.startsWith("http://") || part.startsWith("https://")
      ? <a key={index} href={part} target="_blank" rel="noreferrer">Mở link thanh toán</a>
      : part)}
  </>;
}