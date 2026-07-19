package main

import (
	"database/sql"
	"net/http"
	"strconv"
)

func handler(w http.ResponseWriter, r *http.Request) {
	raw := r.URL.Query().Get("id")
	id, _ := strconv.Atoi(raw)
	query := "SELECT * FROM items WHERE id = " + strconv.Itoa(id)
	db.Query(query)
}

var db *sql.DB
