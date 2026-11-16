import { tx } from "../i18n";
import { type InputHTMLAttributes, useState } from "react";

const Eye = ({ open }: { open: boolean }) => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
    <circle cx="12" cy="12" r="3" />
    {!open && <path d="M4 4l16 16" />}
  </svg>
);

/** Password field with an "eye" button to show what was typed (and hide it again). */
export function PasswordInput({ className, ...props }: Omit<InputHTMLAttributes<HTMLInputElement>, "type">) {
  const [visible, setVisible] = useState(false);
  return (
    <span className={`password-input${className ? ` ${className}` : ""}`}>
      <input {...props} type={visible ? "text" : "password"} />
      <button
        type="button"
        className="eye"
        aria-label={visible ? tx("Masquer le mot de passe") : tx("Afficher le mot de passe")}
        aria-pressed={visible}
        onClick={() => setVisible(!visible)}
      >
        <Eye open={!visible} />
      </button>
    </span>
  );
}
