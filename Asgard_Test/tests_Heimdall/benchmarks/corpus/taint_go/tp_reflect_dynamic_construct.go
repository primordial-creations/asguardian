// TP: WS5 dynamic-construct surfacing. `reflect.ValueOf(...)` reached with
// a non-constant (tainted) operand is a reflective construct whose
// resulting behavior static analysis cannot decide -- must surface an
// explicit needs-review dynamic_construct finding (CWE-470), independent
// of and in addition to normal sink resolution.
package main

import (
	"net/http"
	"reflect"
)

func handler(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	v := reflect.ValueOf(name)
	_ = v
}
