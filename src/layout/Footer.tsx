import { navigateTo } from "../app/routing";

export function Footer() {
  return (
    <footer>
      <button onClick={() => navigateTo("/privacy")}>Privacy Policy</button>
      <span>18+ only</span>
      <span>Payments handled off-site</span>
    </footer>
  );
}



