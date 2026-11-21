"use client";
import { Suspense } from "react";
import LoginForm from "@/components/LoginForm";
import { Loading } from "@/components/Ui";

export default function CitizenLogin() {
  return (
    <Suspense fallback={<Loading />}>
      <LoginForm role="citizen" />
    </Suspense>
  );
}
