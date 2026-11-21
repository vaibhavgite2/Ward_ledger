"use client";
import { Suspense } from "react";
import LoginForm from "@/components/LoginForm";
import { Loading } from "@/components/Ui";

export default function OfficerLogin() {
  return (
    <Suspense fallback={<Loading />}>
      <LoginForm role="officer" />
    </Suspense>
  );
}
