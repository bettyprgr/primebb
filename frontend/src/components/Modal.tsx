import { Button } from "./Button";

export function ConfirmInline({ message, onConfirm }: { message: string; onConfirm: () => void }) {
  return (
    <div className="confirm-inline">
      <span>{message}</span>
      <Button onClick={onConfirm}>Confirm</Button>
    </div>
  );
}
