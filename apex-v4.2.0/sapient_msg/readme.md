# Sapient protocol definitions

Apex contains the definitions for multiple Sapient protocols in protobuf format. Additionally, it
can convert to Sapient v6 from BSI FLEX 335 V1, even though the definition of the former is not
contained in the code explicitly, and is only available when converting to XML.

Having multiple versions of similar protobuf protocols requires a few adjustments:

1. Each protocol lives in it's own subdirectory inside `sapient_msg`
1. `import` statements should be adjusted to import from their own subdirectory, e.g.
   `import "sapient_msg/location.proto";` becomes
   `import "sapient_msg/bsi_flex_335_v1_0/location.proto";`.
1. Each protocol should live within it's own package, e.g. `package sapient_msg` becomes
   `package sapient_msg.bsi_flex_335_v1_0`.
1. There is only one `proto_options.proto` file for all protocols. It lives directly under
   `sapient_msg`. There should no such file living inside each version subdirectory. As a result,
   import statements should be adjusted as necessary.

Finally, `pre-commit` will do the following (assuming it is installed):

1. Create python bindings for all proto files
1. Copy the bindings for the latest protocol to `sapient_msg/latest`

Note that `pre-commit` does not check for extra files. It is possible to regenerate all bindings
with:

```bash
> rm sapient_msg/*_pb2.py
> rm sapient_msg/*_pb2.pyi
> rm sapient_msg/*/*_pb2.py
> rm sapient_mgs/*/*_pb2.pyi
> pre-commit run generate --all
```

This allows `Apex` to simply call `import sapient_msg.latest` where necessary, without worrying
about versions.
