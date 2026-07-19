package main

import "net/http"

func handler(w http.ResponseWriter, r *http.Request) {
	http.Get("https://internal.example.com/health")
}
