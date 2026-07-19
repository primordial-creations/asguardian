// FP sibling of tp_reflect_dynamic_construct.go: `reflect.ValueOf(...)`
// called with a statically-CONSTANT argument must NOT flag -- there is
// nothing dynamic/attacker-influenced about the operand.
package main

import "reflect"

func handler() {
	v := reflect.ValueOf("constant")
	_ = v
}
